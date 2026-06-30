# 11 — AI panel builder (fixed flow + natural-language input)

Still a **fixed-workflow** template, but the "add panel" flow gains an **AI chat**:
an operator types a free-text requirement, the AI engine parses it, picks the right
**predefined** library panel, fills its **parameters**, and builds it — or asks a
clarifying question, or says plainly that it can't. The AI **never generates code**;
it only calls existing tools with inputs. When no template/data can satisfy a
request it says so instead of guessing.

> **No LLM / no cost in this repo.** This repo ships a **free, offline, deterministic**
> engine (`SimulatedAIEngine`) that mimics the parsing for dev & testing, plus a fully
> built **real LLM engine** (`LLMToolEngine`) that is verified offline with a fake LLM
> but **never calls a model here**. The other agent points it at a **local gpt-oss
> endpoint** (OpenAI-compatible) by setting a few env vars — see *Connecting a real LLM*.
> **No LangGraph** — the routing flow is a simple tool-calling loop (see *Why no
> LangGraph*).

## Architecture — the swap seam
```
Frontend AI chat ──POST /panel/ai──▶ AIPanelEngine            (deps.get_ai_panel_engine, by RCA_AI_PROVIDER)
                                        │  simulated = SimulatedAIEngine   ← free/offline, default
                                        │  openai    = LLMToolEngine(LLMClient)
                                        │                 └─ OpenAICompatLLMClient → local gpt-oss (/v1)
                                        ▼  (tool surface — same for both)
                                   ai/tools.py        (in-process; also wrapped by ai/mcp_server.py)
                                     • list_library_panels(template)
                                     • describe_template(template)
                                     • build_panel(template, panel_id, inputs, input_group, params)
                                     • run_skill(name, **args)            # predefined synthesis skills
                                        ▼
                                   engine.run_panel(..., params) → PanelPayload
```
The **tool surface** (`backend/rcalibrary/ai/tools.py`) is the contract; both engines
call it in-process. `LLMToolEngine` adds a thin `LLMClient` seam — the only swap point
for the model. The optional `ai/mcp_server.py` exposes the same tools over MCP for an
out-of-process client, but is not on the runtime path. Switching the engine/LLM never
touches the tools, the skills, the engine interface, or the panel contract.

## The chat protocol — `POST /api/templates/{id}/panel/ai`
Request (`AIPanelRequest`): `{message, session_id?, inputs, input_group}` — omit
`session_id` on the first turn; echo it back to continue the conversation.

Response (`AIPanelResponse`): `{session_id, status, reply, panel?, warnings}` where
`status` ∈:

| status | meaning |
|---|---|
| `needs_input` | a clarifying question (e.g. "which granularity?"); send another turn |
| `panel` | a `PanelPayload` was built — insert it into the report (same contract as library panels) |
| `cannot_satisfy` | nothing in the available templates/data matches — `reply` explains |
| `disabled` | AI is off (`RCA_AI_ENABLED=false`, or the template's `ai_panels` is false) |

The route is gated by the template's `meta.ai_panels` flag and runs the engine off
the event loop (`run_in_threadpool`). Engines never raise to the route — they return
a structured reply.

## Panel parameters (test case A)
Library panels of type `timeseries`/`line`/`bar`/`scatter` accept AI knobs
`date_start` / `date_end` (ISO) / `granularity` (`daily`|`3h`|`hourly`).
`engine.run_panel(..., params=...)` overlays them onto the bundle's analysis-step
`.params`, so analyzers read them via `ctx.params` (unknown keys ignored). No params
→ identical default behavior. The VoC analyzers use shared helpers `_build_grids` /
`_build_volume_ts` / `_resolve_default_gran` so the window/granularity are tunable
without changing the `TimeseriesData` contract.

Example: *"show call volume from 2026-05-01 to 2026-05-20 at hourly granularity"* →
the agent picks `call_volume_trend` and calls `build_panel(..., params={date_start,
date_end, granularity})`.

## Skills (test case B)
A **skill** is a predefined synthesis capability (the only place an LLM runs in
production). Skills live in `backend/rcalibrary/ai/skills/` with a `@skill("name")`
registry (mirrors analyzers). The shipped `summarize_symptoms` is a **deterministic
keyword classifier**: it filters out non-network asks (billing/account) and counts
the distinct users mentioning each network symptom. The `transcript_summary` library
panel is marked **`requires_ai: true`** — hidden from the manual picker, rejected by
the plain `/panel` endpoint (400), and only buildable via the AI chat. Its analyzer
(`voc_transcript_summary`) calls the skill and renders one markdown panel (narrative
+ ranked symptom list).

## requires_ai panels
`LibraryPanel.requires_ai` (default false). When true: hidden from the manual
add-panel picker (frontend filters `requires_ai`), the `POST /panel` endpoint returns
400, and only the AI engine may build it.

## Config (`RCA_AI_*`)
| setting | default | meaning |
|---|---|---|
| `RCA_AI_ENABLED` | `true` | master switch (simulated is free, so on by default) |
| `RCA_AI_PROVIDER` | `simulated` | `simulated` (free/offline) · `openai`/`local`/`gpt-oss` (real LLM) |
| `RCA_AI_BASE_URL` | `""` | OpenAI-compatible endpoint, e.g. `http://localhost:8000/v1` (gpt-oss) |
| `RCA_AI_MODEL` | `""` | model name on that endpoint, e.g. `gpt-oss-20b` |
| `RCA_AI_API_KEY` | `""` | optional; most local gateways ignore it |
| `RCA_AI_REQUEST_TIMEOUT` | `60` | per-request timeout (seconds) |
| `RCA_AI_TEMPERATURE` | `0.0` | deterministic routing |
| `RCA_AI_TOOL_CHOICE` | `required` | force a tool call; set `auto` if your server rejects `required` |
| `RCA_AI_MAX_TURNS` | `12` | safety cap on chat turns per session |
| `RCA_AI_SESSION_TTL_S` | `1800` | drop idle chat sessions after this many seconds |

The shipped `simulated` engine needs **no endpoint, no key, and no extra deps**.

## The real LLM engine — `LLMToolEngine` (no LangGraph)
`LLMToolEngine` ([ai/engine.py](../backend/rcalibrary/ai/engine.py)) is a provider-
agnostic **tool-calling loop**. Each turn it gives the model a closed catalog (the
template's library panels) and **three action tools** it must choose exactly one of —
mapped 1:1 to the response statuses:

| tool | → status |
|---|---|
| `build_panel(panel_id, date_start?, date_end?, granularity?)` | `panel` |
| `ask_clarification(question)` | `needs_input` |
| `cannot_satisfy(reason)` | `cannot_satisfy` |

It validates `panel_id` against the library, coerces params, calls `tools.build_panel`,
and does **one corrective retry** on a bad/unbuildable choice (the error is fed back to
the model); endpoint failures degrade to `cannot_satisfy`. The model talks through a
one-method `LLMClient` ([ai/llm.py](../backend/rcalibrary/ai/llm.py)):
`respond(system, messages, tools, tool_choice) -> LLMReply{tool_call, text}`.

### Why no LangGraph
The flow is one forced tool call per turn over a 4-panel set (plus one retry) — a
shallow classifier, not a cyclic/branching agent. A plain loop is simpler, easier to
make robust on a local model, and **fully testable offline** with a `FakeLLMClient`.
LangGraph is reserved for the future Level-2 agentic flow
([solutions/langgraph_flow.py](../backend/rcalibrary/solutions/langgraph_flow.py)).

## Connecting a real LLM (the other agent, in its env)
The engine + the gpt-oss client are already written and tested offline. To go live:
1. `pip install '.[ai]'` (`openai`; `mcp` only if you want the standalone MCP server).
2. Point it at the local gpt-oss endpoint and select the provider:
   ```bash
   export RCA_AI_PROVIDER=openai
   export RCA_AI_BASE_URL=http://localhost:8000/v1   # your gpt-oss OpenAI-compatible URL
   export RCA_AI_MODEL=gpt-oss-20b
   # export RCA_AI_API_KEY=...   # only if your gateway requires it
   ```
   `deps.get_ai_panel_engine` then builds `LLMToolEngine(OpenAICompatLLMClient(...))`.
3. Confirm your server supports OpenAI **tool/function calling** with
   `tool_choice="required"`. If it only supports `"auto"`, the engine still handles a
   bare-text reply as a clarification — see the `# LLM AGENT:` note in `ai/llm.py` and
   `docs/handoff/ai-panel-llm/05-connect-gpt-oss.md`.

That's the whole integration — **no code to write**, just config (a custom provider can
still register its own engine via `extensions.register_ai_engine`). The tool surface,
the engine interface, the skill interface, and `PanelPayload` are the fixed contract.

The standalone MCP tool server (optional) runs with
`python -m rcalibrary.ai.mcp_server` (needs `mcp`).

## Frontend
The add-panel picker's **"✨ Ask AI to build a panel"** option (enabled when
`ai_panels` is true) opens a **multi-turn chat** (`frontend/js/report/report-ai-chat.js`).
Each turn calls `/panel/ai`; a `panel` reply is inserted into the report via the
existing marker/insert flow and the chat stays open for refinement.
`cannot_satisfy`/`disabled` show the message.

## Ownership (see [09-usecase-handoff.md](09-usecase-handoff.md))
- **STRUCTURE agent**: the MCP tool surface, the simulated engine, the panel output
  templates, the chat UI, and the dummy data.
- **DATA / LLM agent**: the real transcript source, the real LLM engine + skill
  implementation, and real param-aware queries (`# DATA AGENT:` / `# LLM AGENT:`).

## Test cases shipped on the VoC template
- **A** — *"call volume from day X to day Y at granularity N"* → `call_volume_trend`
  (param-tuned timeseries).
- **B** — *"summarize the symptom types from the call transcripts"* →
  `transcript_summary` (requires-AI markdown breakdown via `summarize_symptoms`).

## Out of scope / intentionally simulated
- Real LLM calls (other agent's env); the shipped engine is rule-based.
- A separate-process MCP server (in-memory/stdio for now; transport is the later
  split point).
- Token-streaming UI (request/response chat turns only); persistent multi-user chat
  history (in-memory, TTL'd).
- The AI generating new analyzers/panels/code — forbidden by design.
