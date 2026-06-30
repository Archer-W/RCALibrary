"""LLM client abstraction for the AI panel routing engine.

The routing engine ([engine.py] ``LLMToolEngine``) is provider-agnostic: it talks to an
``LLMClient`` with a single ``respond()`` method that takes a system prompt, the message
history, and a set of tool (function) schemas, and returns the model's chosen tool call.

This repo ships:
  * ``FakeLLMClient`` — deterministic, scripted; drives ALL offline tests (no network).
  * ``OpenAICompatLLMClient`` — for a **local OpenAI-compatible endpoint** (e.g. gpt-oss
    served by vLLM / Ollama / a local gateway). It is **lazy-imported and never run in
    this repo's tests** (no endpoint, no cost). The other agent points it at their
    endpoint via ``RCA_AI_BASE_URL`` / ``RCA_AI_MODEL``.

See docs/11-ai-panel-builder.md and docs/handoff/ai-panel-llm/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class LLMReply:
    """One model turn: either a chosen tool call or plain text."""

    tool_call: dict | None = None  # {"name": str, "arguments": dict}
    text: str | None = None


class LLMClient(ABC):
    @abstractmethod
    def respond(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "required",
    ) -> LLMReply:
        """Return the model's reply. ``messages`` is ``[{role, content}]`` (no system —
        it is passed separately). ``tools`` are OpenAI-style function schemas
        (``{name, description, parameters}``)."""
        ...


def _coerce(item: Any) -> LLMReply:
    """Normalize a fake-script item to an LLMReply. Accepts an LLMReply, a
    ``{tool_call, text}`` dict, a ``{name, arguments}`` tool-call shorthand, or a plain
    string (treated as text)."""
    if isinstance(item, LLMReply):
        return item
    if isinstance(item, str):
        return LLMReply(text=item)
    if isinstance(item, dict):
        if "tool_call" in item or "text" in item:
            return LLMReply(tool_call=item.get("tool_call"), text=item.get("text"))
        if "name" in item:
            return LLMReply(tool_call={"name": item["name"], "arguments": item.get("arguments", {})})
    raise TypeError(f"bad FakeLLMClient script item: {item!r}")


class FakeLLMClient(LLMClient):
    """Offline, deterministic. ``script`` is either a list of replies returned in order
    (LLMReply | ``{name, arguments}`` | ``{tool_call/text}`` | str | Exception), or a
    callable ``(system, messages, tools) -> reply``. An Exception item is raised (to
    exercise endpoint-failure handling)."""

    def __init__(self, script):
        self._script = script
        self._i = 0

    def respond(self, system, messages, tools, tool_choice="required") -> LLMReply:
        if callable(self._script):
            out = self._script(system, messages, tools)
            if isinstance(out, BaseException):
                raise out
            return _coerce(out)
        if self._i >= len(self._script):
            raise AssertionError("FakeLLMClient script exhausted")
        item = self._script[self._i]
        self._i += 1
        if isinstance(item, BaseException):
            raise item
        return _coerce(item)


class OpenAICompatLLMClient(LLMClient):
    """Talks to an OpenAI-compatible Chat Completions endpoint (e.g. a local gpt-oss
    served by vLLM / Ollama). ``openai`` is imported lazily so the base app installs and
    runs without it.

    # LLM AGENT: this is THE swap point. Point it at your endpoint via RCA_AI_BASE_URL /
    # RCA_AI_MODEL (+ RCA_AI_API_KEY if your gateway needs one). If your server rejects
    # tool_choice="required", pass "auto" (set RCA_AI_TOOL_CHOICE) — the engine still
    # handles a bare-text reply as a clarification. See docs/handoff/ai-panel-llm/05.
    """

    def __init__(self, *, base_url, model, api_key="", timeout=60, temperature=0.0, tool_choice="required"):
        self._base_url = base_url
        self._model = model
        self._api_key = api_key or "not-needed"  # local gateways usually ignore the key
        self._timeout = timeout
        self._temperature = temperature
        self._tool_choice = tool_choice  # config override (RCA_AI_TOOL_CHOICE); wins over the call arg
        self._client = None  # lazily constructed openai.OpenAI

    def _ensure(self):
        if self._client is None:
            try:
                import openai
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    "The 'openai' package is required for the OpenAI-compatible LLM client. "
                    "Install it with: pip install '.[ai]'."
                ) from exc
            self._client = openai.OpenAI(
                base_url=self._base_url, api_key=self._api_key, timeout=self._timeout
            )
        return self._client

    def respond(self, system, messages, tools, tool_choice="required") -> LLMReply:
        import json

        client = self._ensure()
        oa_messages = [{"role": "system", "content": system}] + [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]
        oa_tools = [{"type": "function", "function": t} for t in tools]
        resp = client.chat.completions.create(
            model=self._model,
            messages=oa_messages,
            tools=oa_tools,
            tool_choice=self._tool_choice or tool_choice,
            temperature=self._temperature,
        )
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            call = tool_calls[0]
            raw = getattr(call.function, "arguments", None) or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except Exception:  # noqa: BLE001 - model emitted malformed JSON args
                args = {}
            return LLMReply(tool_call={"name": call.function.name, "arguments": args})
        return LLMReply(text=(getattr(msg, "content", None) or "").strip() or None)
