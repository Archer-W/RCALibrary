# 06 — Verification

## Offline (no endpoint, no cost) — run after each layer
```bash
python -m pytest -q
```
What proves what:
- `tests/unit/test_panel_library.py`, `tests/api/test_panel_customize.py` — Layer 1.
- `tests/unit/test_ai_panel.py`, `tests/api/test_ai_panel.py` — Layer 2 (simulated engine,
  `/panel/ai` multi-turn, `requires_ai` 400 guard).
- `tests/unit/test_ai_llm_engine.py` — **Layer 3**: drives `LLMToolEngine` with a
  `FakeLLMClient` (clarify→build with params applied, one-shot, cannot-satisfy, invalid
  panel_id→retry→decline, endpoint-error→graceful, transcript routing, max-turns) and tests
  the `OpenAICompatLLMClient` response parsing with a fake `openai` client. **If this is
  green, your merge of the LLM engine is correct — before any model is involved.**

The `mcp` test self-skips when `mcp` isn't installed (expected; it's optional).

On a fresh checkout, regenerate demo data first: `python data/samples/ana.rca.netcare-voc-trend/generate_dummy.py`.
(Your branch uses real data, so adapt to your pulls instead.)

## Live (against your gpt-oss endpoint) — after Layer 3 config
1. Headless smoke: run the script in `05-connect-gpt-oss.md` → expect
   `panel -> timeseries`, then `panel -> markdown`, then `cannot_satisfy`.
2. UI: `./run.sh` (with the `RCA_AI_*` env vars set) → run `T-1001` (or a real trend on
   your data) → **+ Add panel → ✨ Ask AI** →
   - "call volume from 2026-06-01 to 2026-06-05 hourly" → a param-tuned timeseries is inserted;
   - an ambiguous ask ("show call volume") → a clarifying question, then answer it → panel;
   - "summarize the symptom types from the call transcripts" → the markdown breakdown
     (deterministic skill; routing via your LLM);
   - "export the report to PDF" → a plain decline.

## Confidence checklist
- [ ] `pytest -q` green on your branch (Layers you integrated).
- [ ] "Ask AI" works with `RCA_AI_PROVIDER=simulated` (no endpoint) — proves the wiring.
- [ ] `tests/unit/test_ai_llm_engine.py` green — proves the LLM engine merge.
- [ ] Live smoke returns `panel` for the call-volume request against gpt-oss.
- [ ] An impossible request returns `cannot_satisfy` (the model declines, not hallucinates).
