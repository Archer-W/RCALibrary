# 05 — Connect your local gpt-oss endpoint

The routing engine and the OpenAI-compatible client are already built. Going live is
**config only** (no code to write).

## Prerequisites
- A running **gpt-oss** model behind an **OpenAI-compatible** Chat Completions API
  (e.g. vLLM `--api-server`, Ollama's `/v1`, or a local gateway) that supports
  **tool / function calling**.
- `pip install '.[ai]'` (adds `openai`).

## Configure (env vars)
```bash
export RCA_AI_ENABLED=1
export RCA_AI_PROVIDER=openai                       # or local / gpt-oss
export RCA_AI_BASE_URL=http://localhost:8000/v1     # your OpenAI-compatible endpoint
export RCA_AI_MODEL=gpt-oss-20b                      # the model name your server serves
# export RCA_AI_API_KEY=...        # only if your gateway requires a key
# export RCA_AI_TEMPERATURE=0.0    # deterministic routing (default)
# export RCA_AI_TOOL_CHOICE=required   # set to "auto" if your server rejects "required"
```
`deps.get_ai_panel_engine()` then builds
`LLMToolEngine(OpenAICompatLLMClient(base_url, model, ...))`. The template must also have
`meta.ai_panels: true` (already set on the VoC template).

## The swap point (if you need to customize transport)
`backend/rcalibrary/ai/llm.py` → `OpenAICompatLLMClient` (marked `# LLM AGENT:`). It does a
single `client.chat.completions.create(model, messages, tools, tool_choice, temperature)`
and parses `choices[0].message.tool_calls[0]`. If your server differs, this is the only
file to touch (e.g. swap the `openai` SDK for raw `httpx`, add headers, or adjust parsing).
Everything upstream (`LLMToolEngine`, tools, statuses, UI) is unaffected.

## Server flags that matter (local models)
- **Tool calling must be enabled.** vLLM: serve with a tool-call parser
  (`--enable-auto-tool-choice --tool-call-parser ...`). Ollama: a recent build with tool
  support. If the model never returns `tool_calls`, the engine treats the text as a
  clarification — you'll see `needs_input` instead of `panel`. That's the symptom of
  tool-calling not being on.
- **`tool_choice="required"`** forces exactly one action tool (best reliability). If your
  server errors on `"required"`, set `RCA_AI_TOOL_CHOICE=auto`; the engine still maps a
  bare-text reply to a clarification, but the model may sometimes chat instead of calling
  a tool — tighten the prompt if so.
- **Context window:** the system prompt embeds the panel catalog (small) + the chat
  history (short). Default context is fine; no long-context server config needed.

## Live smoke (no UI)
```bash
RCA_AI_ENABLED=1 RCA_AI_PROVIDER=openai \
RCA_AI_BASE_URL=http://localhost:8000/v1 RCA_AI_MODEL=gpt-oss-20b \
PYTHONPATH="backend:." python - <<'PY'
from rcalibrary.deps import get_ai_panel_engine, get_template_registry
eng = get_ai_panel_engine()                      # -> LLMToolEngine
t = get_template_registry().get("ana.rca.netcare-voc-trend")
g = dict(template=t, inputs={"trend_id": "T-1001"}, input_group="trend_id", principal=None)
r = eng.chat(None, "show call volume from 2026-06-01 to 2026-06-05 hourly", **g)
print(r["status"], "->", (r["panel"].type if r["panel"] else r["reply"][:80]))
PY
```
Expect `panel -> timeseries`. Then `summarize the symptom types from the call transcripts`
→ `panel -> markdown`; `export to PDF` → `cannot_satisfy`.

## Troubleshooting
| symptom | likely cause | fix |
|---|---|---|
| always `needs_input` / chatty | tool calling off, or `tool_choice` ignored | enable the server's tool-call parser; keep `RCA_AI_TOOL_CHOICE=required` |
| `cannot_satisfy: AI service unavailable (...)` | bad `RCA_AI_BASE_URL`, server down, or auth | check the URL ends in `/v1`, server is up, set `RCA_AI_API_KEY` if required |
| 400 on `tool_choice` | server doesn't support `"required"` | `export RCA_AI_TOOL_CHOICE=auto` |
| picks the wrong panel / bad params | weak model / prompt | lower `RCA_AI_TEMPERATURE`, tighten the catalog descriptions in `template.yaml`, or refine the system prompt in `LLMToolEngine._prompt_and_tools` |
| `disabled` status | `ai_panels` false, `RCA_AI_ENABLED=0`, or empty `RCA_AI_BASE_URL` | set the template flag + the env vars |

## Optional: override the deterministic synthesis skill with your LLM (later)
Synthesis is deferred, but when you want it: register an LLM-backed skill under the same
name — `@skill("summarize_symptoms")` in a plugin on `RCA_PLUGINS` (last registration
wins). Keep the output shape `{summary, breakdown:[{symptom_type, n_users, n_mentions,
share}]}` so the transcript panel renders unchanged. The routing engine is unaffected.
