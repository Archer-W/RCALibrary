# 04 — Integration steps (porting onto your diverged branch)

A blind `git merge` won't work cleanly (your `usecases/netcare_voc.py`, template YAML, and
data differ). Port by layer, verifying after each. Run all commands from the repo root.

## 0. Prep
- Branch off your work: `git switch -c integrate-ai-panels`.
- Have `ai-panel-feature.patch` and `03-changeset.md` open side by side.
- Optional first attempt: `git apply --3way --reject ai-panel-feature.patch`. Expect the
  **✅ new files** to apply and the **✋ diverged files** (`usecases/netcare_voc.py`,
  `template.yaml`) to `.rej` — handle those by hand per `03`. (`git apply` won't add the
  new files unless they're in the patch — they are, via intent-to-add; if your `git`
  refuses, just copy the new files from the delivered tree.)

## Layer 1 — customizable panels (skip if you already have it)
*Do you already have `panel_library`, `ReportController` add/remove/save, and
`/templates/{id}/panel` + `/save`?* If yes → skip to Layer 2.
1. Copy ✅ new files: `backend/rcalibrary/persistence/`, `frontend/js/report/report-customize.js`,
   `docs/10-*`, the L1 tests.
2. Merge ⚠️ blocks: `config.py` (cache), `deps.py` (`get_report_cache`), `models.py`
   (`PanelType` pie/flow/stat_group, `PanelEncoding`, `LibraryPanel`, `Template.panel_library`
   + validation), `report_builder.py` (`_fill_pie`/`_fill_stat_group`), `loader.py`,
   `reporting/contract.py`, `solutions/base.py` (`from_cache`), `api/routes_templates.py`
   (`/panel`, `/save`, `/run` cache, `get_template`), `api/schemas.py`, `.gitignore`,
   `tests/conftest.py`, the frontend panels/CSS/`endpoints.js`/`report-view.js`/`view-runner.js`.
3. ✋ `usecases/netcare_voc.py` + `template.yaml`: add the L1 library panels (`complaint_pie`,
   `rrc_kpi`) and their analyzers **only if you don't already have equivalents**.
4. Verify: `python -m pytest -q tests/unit/test_panel_library.py tests/api/test_panel_customize.py`.

## Layer 2 — AI mode + simulated engine
1. Copy ✅ new files: **`backend/rcalibrary/ai/`** (whole package), `frontend/js/report/report-ai-chat.js`,
   `docs/11-*`, `tests/unit/test_ai_panel.py`, `tests/api/test_ai_panel.py`.
2. Merge ⚠️ blocks:
   - `workflow/models.py`: `TemplateMeta.ai_panels`, **`LibraryPanel.requires_ai`**.
   - `workflow/engine.py`: the **`params=` overlay** in `run_panel` (see `03`).
   - `api/routes_templates.py`: the real **`POST /panel/ai`** + the **`requires_ai` 400 guard** in `POST /panel`.
   - `api/schemas.py`: `AIPanelRequest`, `AIPanelResponse`, `PanelLibraryPreview.requires_ai`.
   - `config.py`: `ai_enabled`/`ai_provider`/`ai_max_turns`/`ai_session_ttl_s`.
   - `deps.py`: `get_ai_panel_engine()` (simulated + extensions hook).
   - `extensions.py`: `register_ai_engine`/`get_ai_engine_factory`.
   - frontend: `report-view.js` `_addPanelAI` + `__ai__` branch; `report-customize.js`
     `requires_ai` filter; `endpoints.js` `aiPanelChat`; `components.css` `.ai-chat*`;
     `view-runner.js` pass `inputs`/`inputGroup`/`aiPanels`.
3. ✋ `usecases/netcare_voc.py`: re-apply the **param-aware helpers** + `voc_call_volume_trend`
   + `voc_transcript_summary` into your real analyzers (the *intent* in `03`). The crucial
   bit: your analyzers must read `ctx.params["date_start"/"date_end"/"granularity"]`.
4. ✋ `template.yaml`: set `meta.ai_panels: true`; add the `call_volume_trend` and
   `transcript_summary` (`requires_ai: true`) library panels (wired to your pull ids).
5. 🗑 transcripts: add a transcript data pull (your real source) with columns
   `usid, call_time, transcript_text` (or adapt the analyzer to your columns).
6. Verify (still no LLM — simulated default): `python -m pytest -q tests/unit/test_ai_panel.py tests/api/test_ai_panel.py`
   and click "Ask AI" in the UI (it uses the simulated engine).

## Layer 3 — connect your gpt-oss LLM
1. The code is already in `ai/llm.py` + `ai/engine.py` (`LLMToolEngine`) + the `deps.py`
   provider branch + `config.py` `ai_base_url`/etc — all delivered in Layers 2–3 above.
   Merge the `deps.py` provider branch and the L3 `config.py` settings if not already.
2. `pip install '.[ai]'` (adds `openai`).
3. Configure + smoke-test per **`05-connect-gpt-oss.md`**.
4. Verify offline first: `python -m pytest -q tests/unit/test_ai_llm_engine.py` (drives the
   loop with a fake LLM — proves your merge is correct before involving the model).

## Conflict-prone files (watch these)
| file | why | how |
|---|---|---|
| `usecases/netcare_voc.py` | you rewrote analyzers for real data | re-apply intent (`03` ✋); ensure `ctx.params` is read |
| `template.yaml` | your data_pulls/analysis differ | hand-merge the library panels + `ai_panels`; fix pull-id refs |
| `api/routes_templates.py` | large file, several additions | apply each block; keep your data wiring |
| `deps.py` / `config.py` | central, both layers touch them | additive — append the new factories/settings |

## Done when
`python -m pytest -q` is green on your branch, the "Ask AI" chat builds a panel via the
simulated engine, and (after Layer 3 config) the same works against your gpt-oss endpoint.
