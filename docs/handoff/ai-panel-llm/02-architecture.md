# 02 — Architecture

## The pieces (all under `backend/rcalibrary/`)
```
api/routes_templates.py  POST /templates/{id}/panel/ai   (AIPanelRequest -> AIPanelResponse)
        │  Depends(get_ai_panel_engine)            run off the event loop (run_in_threadpool)
        ▼
deps.get_ai_panel_engine()        selects by RCA_AI_PROVIDER:
        ├─ "simulated" → ai.engine.SimulatedAIEngine          (rule-based, free/offline, DEFAULT)
        └─ "openai"/"local"/"gpt-oss" → ai.engine.LLMToolEngine(OpenAICompatLLMClient(...))
                                            │
                                            ├─ ai.llm.LLMClient.respond(system, messages, tools, tool_choice)
                                            │     └─ OpenAICompatLLMClient → your gpt-oss /v1 (lazy `import openai`)
                                            ▼  both engines call the SAME tool surface, in-process:
                                       ai.tools  • list_library_panels(template)
                                                 • describe_template(template)
                                                 • build_panel(engine, template, panel_id, inputs, input_group, params, principal)
                                                 • run_skill(name, **args)
                                            ▼
                                       workflow.engine.TemplateEngine.run_panel(..., params)  →  PanelPayload
```
`ai/mcp_server.py` wraps the same `ai/tools.py` as an MCP server (optional, out-of-process;
**not on the runtime path** — both engines call `tools` directly).

## Key contracts (do not change these — they're the integration surface)

**`AIPanelEngine`** (`ai/engine.py`): one method —
```python
chat(session_id, message, *, template, inputs, input_group, principal) -> dict
# returns {"session_id", "status", "reply", "panel": PanelPayload|None, "warnings": [str]}
# status ∈ {"needs_input", "panel", "cannot_satisfy", "disabled"}
```
The HTTP layer (`AIPanelRequest`/`AIPanelResponse` in `api/schemas.py`) is a thin wrapper.

**`LLMClient`** (`ai/llm.py`): one method —
```python
respond(system: str, messages: list[{role, content}], tools: list[func_schema],
        tool_choice="required") -> LLMReply{tool_call: {name, arguments} | None, text: str | None}
```
- `FakeLLMClient(script)` — offline, scripted; drives all tests.
- `OpenAICompatLLMClient(base_url, model, api_key, timeout, temperature)` — your gpt-oss
  adapter; lazy-imports `openai`. **This is the only swap point for the model.**

**`LLMToolEngine`** (`ai/engine.py`) — the routing loop. Each turn it gives the model the
closed panel catalog + **three action tools** (forced `tool_choice`), mapped 1:1 to statuses:

| tool the model calls | → status |
|---|---|
| `build_panel(panel_id, date_start?, date_end?, granularity?)` | `panel` |
| `ask_clarification(question)` | `needs_input` |
| `cannot_satisfy(reason)` | `cannot_satisfy` |

It validates `panel_id` against the library, coerces params, calls `tools.build_panel`,
and does **one corrective retry** on a bad/unbuildable choice (feeding the error back).
Endpoint failure → `cannot_satisfy` ("service unavailable"). Multi-turn = an in-memory
session history (`_SessionStore`, TTL + `max_turns`).

**Panel parameters** — library panels of type `timeseries`/`line`/`bar`/`scatter` accept
`date_start`/`date_end`/`granularity`. `run_panel(..., params=...)` overlays them onto the
bundle's analysis-step `.params`, so analyzers read them via `ctx.params` (unknown keys
ignored). No params → default behavior.

**Skills** (`ai/skills/`) — predefined synthesis functions (`@skill`). `summarize_symptoms`
ships **deterministic** (no LLM). Panels marked `requires_ai: true` (e.g. the transcript
summary) are hidden from the manual picker and only built via the AI chat.

## Why this minimizes your effort
Everything except the model call is built and tested offline. The `LLMToolEngine` loop,
the tool surface, the statuses, the param overlay, the frontend chat — all verified with a
`FakeLLMClient`. You only point `OpenAICompatLLMClient` at your gpt-oss endpoint (config),
confirm its tool-calling flags, and optionally tune the system prompt for your model.
