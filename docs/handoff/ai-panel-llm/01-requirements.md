# 01 — Requirements & decisions

## The feature
A **fixed-workflow** template gains an **AI input mode**: an operator types a natural-
language requirement in an "Ask AI" chat; the engine parses it, picks the right
**predefined** library panel, fills its **parameters** (date range, granularity), and
builds it — or asks one clarifying question, or says plainly it can't. The AI **never
generates code**; it only calls existing tools with inputs. When no template/data can
satisfy a request, it says so rather than guessing.

This sits in the **fixed-workflow category** (Level 1), not the future agentic Level 2.

## Decisions (and why) — these shaped the design
| decision | rationale |
|---|---|
| **Local gpt-oss endpoint** (OpenAI-compatible) is the LLM | the only model available to you; no external API/CLI. Integration = an OpenAI-style client pointed at your `base_url`. |
| **No LangGraph** | the routing flow is a shallow classifier (≤1 tool call/turn over a 4-panel set). A plain tool-calling loop is simpler, more robust on a local model, and fully testable offline. LangGraph is reserved for the future Level-2 agentic flow. |
| **Simulated engine stays the default** | dev/CI run free/offline (`RCA_AI_PROVIDER=simulated`); the LLM path is opt-in via config. |
| **Synthesis deferred** | digesting many ticket notes/transcripts with an LLM is a *separate* job (a "skill"); for now the transcript panel uses a **deterministic** stand-in skill. Only *routing* uses the LLM. |
| **AI = constrained tool-caller** | the model only chooses a predefined panel + params (or asks/declines). It cannot invent panels or write code. This is what makes a local model reliable and the surface small. |
| **Structured tool choice** | the model must call exactly one of three action tools (`build_panel` / `ask_clarification` / `cannot_satisfy`) mapped 1:1 to response statuses — no free-text parsing. |

## What "done" looks like for you
You set `RCA_AI_PROVIDER=openai`, `RCA_AI_BASE_URL`, `RCA_AI_MODEL`, run the app, and:
- "show call volume from 2026-06-01 to 2026-06-05 hourly" → a param-tuned timeseries panel;
- an ambiguous ask → a clarifying question;
- an impossible ask ("export to PDF") → a plain decline.

No engine code to write — only config + (optionally) prompt tuning for your model. See
`05-connect-gpt-oss.md`.

## Non-goals (intentionally out of scope here)
- LLM **synthesis** of transcripts/ticket notes (the transcript panel stays deterministic).
- LangGraph / agent graphs.
- Token-streaming chat UI (request/response turns only).
- Persistent / multi-process chat history (in-memory, TTL'd).
