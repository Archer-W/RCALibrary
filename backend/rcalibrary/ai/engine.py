"""AI panel engines — the swappable client of the tool surface.

``AIPanelEngine`` is the interface the ``/panel/ai`` route depends on. This repo
ships ``SimulatedAIEngine``: a FREE, OFFLINE, deterministic engine that mimics what
an LLM would do — keyword-routes a request to a predefined library panel, extracts
date-range/granularity, asks a clarifying question when needed (multi-turn), and
builds the panel via the ``tools`` surface. No LLM, no API key, no cost.

The other agent connects a real LLM by adding an engine for a different
``RCA_AI_PROVIDER`` (e.g. a LangGraph + Claude MCP client against ``ai/mcp_server``)
and selecting it in ``deps.get_ai_panel_engine``. The interface, the tool surface,
and the panel contract are the fixed seam. See docs/11-ai-panel-builder.md.
"""

from __future__ import annotations

import re
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

from . import tools
from .llm import LLMClient

_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_LAST_N_DAYS = re.compile(r"\b(?:last|past|previous)\s+(\d+)\s+day")

# Keyword rules: (trigger phrases, library panel id). First match whose panel
# actually exists in the template's library wins. Order matters — transcript
# (symptom) intent is checked before the complaint pie so "symptom" requests that
# also mention "complaint" route to the transcript summary.
_INTENT_RULES: list[tuple[tuple[str, ...], str]] = [
    (("transcript", "symptom", "symptoms", "what are customers", "what customers"), "transcript_summary"),
    (("rrc", "kpi", "connected user", "ran kpi", "radio"), "rrc_kpi"),
    (("complaint", "distribution", "complaint type"), "complaint_pie"),
    (("call volume", "care call", "call-volume", "volume of call", "calls over", "call trend"),
     "call_volume_trend"),
]


def _norm_gran(text: str) -> str | None:
    # Bare "day"/"hour" are NOT treated as a granularity (avoids matching the word
    # "day" inside a date range like "day X to day Y"); only explicit forms count.
    if any(k in text for k in ("3-hour", "3 hour", "3h", "three-hour", "3-hourly", "3 hourly")):
        return "3h"
    if "hourly" in text:
        return "hourly"
    if "daily" in text:
        return "daily"
    return None


def _extract_params(message: str) -> dict[str, Any]:
    """Pull date_start/date_end/granularity out of a free-text message
    (deterministic — the LLM would do this fuzzier)."""
    m = message.lower()
    params: dict[str, Any] = {}
    gran = _norm_gran(m)
    if gran:
        params["granularity"] = gran
    dates = _ISO_DATE.findall(message)
    if len(dates) >= 2:
        lo, hi = sorted(dates[:2])
        params["date_start"], params["date_end"] = lo, hi
    elif len(dates) == 1:
        params["date_start"] = dates[0]
    else:
        mlast = _LAST_N_DAYS.search(m)
        if mlast:
            n = int(mlast.group(1))
            params["date_start"] = (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%d")
        elif "past week" in m or "last week" in m:
            params["date_start"] = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    return params


def _params_phrase(params: dict[str, Any]) -> str:
    bits = []
    if params.get("granularity"):
        label = {"3h": "3-hourly"}.get(params["granularity"], params["granularity"])
        bits.append(label)
    if params.get("date_start") and params.get("date_end"):
        bits.append(f"{params['date_start']} → {params['date_end']}")
    elif params.get("date_start"):
        bits.append(f"from {params['date_start']}")
    return f" ({', '.join(bits)})" if bits else ""


class AIPanelEngine(ABC):
    """One chat turn: take the user's message + session id, return a structured
    reply (``needs_input`` | ``panel`` | ``cannot_satisfy`` | ``disabled``)."""

    @abstractmethod
    def chat(self, session_id, message, *, template, inputs, input_group, principal) -> dict:
        ...


class DisabledAIEngine(AIPanelEngine):
    def chat(self, session_id, message, *, template, inputs, input_group, principal) -> dict:
        return {
            "session_id": session_id or uuid.uuid4().hex,
            "status": "disabled",
            "reply": "AI panel building is turned off in this deployment.",
            "panel": None,
            "warnings": [],
        }


class _SessionStore:
    """Tiny TTL'd in-memory session store shared by the AI engines. A session is a dict
    with at least ``{updated, turns}`` plus engine-specific fields (e.g. ``pending`` for
    the simulated engine, ``history`` for the LLM engine)."""

    def __init__(self, ttl_s: int, max_turns: int):
        self._ttl_s = ttl_s
        self.max_turns = max_turns
        self._sessions: dict[str, dict[str, Any]] = {}

    def begin(self, session_id, defaults: dict):
        """Prune stale sessions, get-or-create this one, stamp it, bump the turn
        counter. Returns ``(session_id, state)``."""
        cutoff = time.time() - self._ttl_s
        for s in [s for s, st in self._sessions.items() if st["updated"] < cutoff]:
            del self._sessions[s]
        sid = session_id or uuid.uuid4().hex
        st = self._sessions.get(sid)
        if st is None:
            st = {"updated": 0.0, "turns": 0, **defaults}
            self._sessions[sid] = st
        st["updated"] = time.time()
        st["turns"] += 1
        return sid, st

    def drop(self, sid) -> None:
        self._sessions.pop(sid, None)


class SimulatedAIEngine(AIPanelEngine):
    """Deterministic, offline stand-in for the real LLM engine."""

    def __init__(self, engine, *, ttl_s: int = 1800, max_turns: int = 12):
        self._engine = engine  # the TemplateEngine (for build_panel)
        self._store = _SessionStore(ttl_s, max_turns)

    # -- the chat turn --------------------------------------------------------
    def chat(self, session_id, message, *, template, inputs, input_group, principal) -> dict:
        sid, st = self._store.begin(session_id, {"pending": None})
        msg = (message or "").strip()

        if st["turns"] > self._store.max_turns:
            self._store.drop(sid)
            return self._reply(sid, "cannot_satisfy",
                               "This conversation got long — start a fresh panel request.")

        pending = st.get("pending")
        panel_id = pending["panel_id"] if pending else self._match(template, msg)
        if not panel_id:
            return self._reply(sid, "cannot_satisfy", self._menu(template, msg))

        bundle = template.library_panel_by_id(panel_id)
        accepts_params = bool(tools.panel_params(bundle.panel))
        params = dict(pending["params"]) if pending else {}
        params.update(_extract_params(msg))

        # Multi-turn: a tunable chart with no granularity yet -> ask once, then build.
        if accepts_params and not params.get("granularity") and not (pending and pending.get("asked")):
            st["pending"] = {"panel_id": panel_id, "params": params, "asked": True}
            return self._reply(
                sid, "needs_input",
                f"I can build **{bundle.title}**. What granularity — daily, 3-hourly, or hourly? "
                f"You can also give a date range (e.g. 2026-05-01 to 2026-05-20).",
            )
        if accepts_params and not params.get("granularity"):
            params["granularity"] = "daily"  # already asked -> sensible default, don't loop

        try:
            panel, warnings = tools.build_panel(
                self._engine, template, panel_id, inputs, input_group, params, principal
            )
        except Exception as exc:  # noqa: BLE001 - surface a plain message, never 500
            st["pending"] = None
            return self._reply(sid, "cannot_satisfy",
                               f"I matched **{bundle.title}** but couldn't build it: {exc}")

        st["pending"] = None
        return {
            "session_id": sid,
            "status": "panel",
            "reply": f"Here's **{bundle.title}**{_params_phrase(params)}. "
                     f"Drag, resize, or remove it like any panel.",
            "panel": panel,
            "warnings": list(warnings),
        }

    # -- helpers --------------------------------------------------------------
    def _match(self, template, message: str) -> str | None:
        m = message.lower()
        for kws, pid in _INTENT_RULES:
            if any(k in m for k in kws) and template.library_panel_by_id(pid):
                return pid
        return None

    def _menu(self, template, message: str) -> str:
        titles = [b["title"] for b in tools.list_library_panels(template)]
        if not titles:
            return "There are no AI-buildable panels for this report."
        listed = "; ".join(titles)
        return (
            "I can only build panels from this report's available templates and data: "
            f"{listed}. I couldn't match your request to one of them — try rephrasing, "
            "or pick a panel from that list."
        )

    def _reply(self, sid, status, reply) -> dict:
        return {"session_id": sid, "status": status, "reply": reply, "panel": None, "warnings": []}


# --- Real LLM engine: a constrained tool-calling loop over a local endpoint ---
# Provider-agnostic — it drives any `LLMClient` (gpt-oss via OpenAICompatLLMClient now,
# anything else later). The model MUST pick exactly one of three action tools that map
# 1:1 to the response statuses. No LangGraph: the flow is a single forced tool call per
# turn (with one corrective retry on a bad/unbuildable choice). See docs/11 +
# docs/handoff/ai-panel-llm/.

_GRAN_VALUES = ["daily", "3h", "hourly"]


def _status(sid, status, reply, panel=None, warnings=None) -> dict:
    return {"session_id": sid, "status": status, "reply": reply, "panel": panel,
            "warnings": list(warnings or [])}


class LLMToolEngine(AIPanelEngine):
    """Route a free-text request to a predefined panel using a real LLM over a tool-
    calling loop. The LLM only chooses a panel + params (or asks / declines) — it never
    generates code or invents panels. Multi-turn via an in-memory session history."""

    def __init__(self, engine, llm: LLMClient, *, ttl_s: int = 1800, max_turns: int = 12):
        self._engine = engine
        self._llm = llm
        self._store = _SessionStore(ttl_s, max_turns)

    def chat(self, session_id, message, *, template, inputs, input_group, principal) -> dict:
        sid, st = self._store.begin(session_id, {"history": []})
        if st["turns"] > self._store.max_turns:
            self._store.drop(sid)
            return _status(sid, "cannot_satisfy", "This conversation got long — start a fresh panel request.")

        history = st["history"]
        history.append({"role": "user", "content": (message or "").strip()})
        system, tool_schemas = self._prompt_and_tools(template)
        panel_ids = [b["id"] for b in tools.list_library_panels(template)]

        correction = None
        for _ in range(2):  # one corrective retry on a bad/unbuildable choice
            msgs = history if correction is None else history + [{"role": "user", "content": correction}]
            try:
                reply = self._llm.respond(system, msgs, tool_schemas, tool_choice="required")
            except Exception as exc:  # noqa: BLE001 - endpoint down / transport error
                return _status(sid, "cannot_satisfy", f"The AI service is unavailable right now ({exc}).")

            call = reply.tool_call
            if not call:  # model returned text despite forced tools -> treat as a question
                q = (reply.text or "Could you clarify what you'd like to see?").strip()
                history.append({"role": "assistant", "content": q})
                return _status(sid, "needs_input", q)

            name = call.get("name")
            args = call.get("arguments") or {}
            if name == "ask_clarification":
                q = str(args.get("question") or "Could you clarify what you'd like to see?")
                history.append({"role": "assistant", "content": q})
                return _status(sid, "needs_input", q)
            if name == "cannot_satisfy":
                return _status(sid, "cannot_satisfy",
                               str(args.get("reason") or "I can't build that from the available panels."))
            if name == "build_panel":
                pid = str(args.get("panel_id") or "")
                bundle = template.library_panel_by_id(pid)
                if bundle is None:
                    correction = (f'"{pid}" is not an available panel. Choose panel_id from {panel_ids}, '
                                  "or call cannot_satisfy if none fits.")
                    continue
                params = {k: args[k] for k in ("date_start", "date_end", "granularity") if args.get(k)}
                try:
                    panel, warnings = tools.build_panel(
                        self._engine, template, pid, inputs, input_group, params, principal
                    )
                except Exception as exc:  # noqa: BLE001 - surface plainly, retry once
                    correction = f"Building '{pid}' failed: {exc}. Try different parameters or call cannot_satisfy."
                    continue
                history.append({"role": "assistant", "content": f"Built {bundle.title}."})
                return _status(sid, "panel",
                               f"Here's **{bundle.title}**{_params_phrase(params)}. "
                               "Drag, resize, or remove it like any panel.",
                               panel, warnings)
            correction = "Use exactly one of: build_panel, ask_clarification, cannot_satisfy."

        return _status(sid, "cannot_satisfy",
                       "I couldn't map your request to an available panel. Try naming one of the "
                       "listed panels, or give a clearer date range / granularity.")

    # -- prompt + tool schemas ------------------------------------------------
    def _prompt_and_tools(self, template):
        """Build the system prompt (with the closed panel catalog) + the 3 action-tool
        schemas. Exposed for tests."""
        catalog = tools.list_library_panels(template)
        panel_ids = [b["id"] for b in catalog]
        lines = []
        for b in catalog:
            ptxt = ", ".join(b["params"]) if b["params"] else "none"
            ai = " (AI-only)" if b.get("requires_ai") else ""
            lines.append(f"- id={b['id']} | {b['title']}{ai} — {b['description']} | params: {ptxt}")
        catalog_txt = "\n".join(lines) if lines else "(no panels available)"
        system = (
            "You build ONE data panel for a network root-cause report by choosing from a "
            "FIXED catalog of predefined panels. You do NOT write code or invent panels.\n"
            "For each user message call EXACTLY ONE tool:\n"
            "- build_panel: the request clearly maps to one catalog panel. Set panel_id, and "
            "only for time-series panels set date_start/date_end (YYYY-MM-DD) and granularity "
            "if the user gave them.\n"
            "- ask_clarification: you need one missing detail (e.g. which granularity).\n"
            "- cannot_satisfy: no catalog panel can satisfy the request.\n\n"
            f"Catalog (choose panel_id ONLY from these ids):\n{catalog_txt}\n\n"
            "Extract dates/granularity from the user's words; do not invent a date range that "
            "was not requested. Keep replies short."
        )
        date_prop = {"type": "string", "description": "ISO date YYYY-MM-DD"}
        tool_schemas = [
            {
                "name": "build_panel",
                "description": "Build one predefined panel, optionally with a date range/granularity.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "panel_id": {"type": "string", "enum": panel_ids,
                                     "description": "Which catalog panel to build."},
                        "date_start": date_prop,
                        "date_end": date_prop,
                        "granularity": {"type": "string", "enum": _GRAN_VALUES},
                    },
                    "required": ["panel_id"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "ask_clarification",
                "description": "Ask the user one short question to resolve a missing detail.",
                "parameters": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "cannot_satisfy",
                "description": "State plainly that no available panel can satisfy the request.",
                "parameters": {
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                    "additionalProperties": False,
                },
            },
        ]
        return system, tool_schemas
