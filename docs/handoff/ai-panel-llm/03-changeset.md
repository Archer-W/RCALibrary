# 03 — Changeset (delta from `HEAD`)

Every change is tagged with its **layer** (L1 customizable panels · L2 AI mode + simulated
engine · L3 gpt-oss LLM engine) and its **integration class**: **✅ new** · **⚠️ shared
edit** · **✋ diverged (re-apply intent)** · **🗑 demo-only**. Exact lines are in
`ai-panel-feature.patch` (50 files; CSVs excluded). Stats: ~2.8k insertions across 34
tracked files + 14 new files.

---

## ✅ New files — drop in (won't conflict; they don't exist on `HEAD`)

**Backend — AI package** (`backend/rcalibrary/ai/`)
| file | layer | purpose |
|---|---|---|
| `ai/__init__.py` | L2/L3 | exports the engines + LLM client classes |
| `ai/tools.py` | L2 | the **tool surface**: `list_library_panels`, `describe_template`, `build_panel`, `run_skill`, `panel_params` |
| `ai/engine.py` | L2/L3 | `AIPanelEngine` (ABC), `DisabledAIEngine`, `SimulatedAIEngine` (L2), `_SessionStore` + `LLMToolEngine` (L3) |
| `ai/llm.py` | L3 | `LLMClient`, `LLMReply`, `FakeLLMClient`, `OpenAICompatLLMClient` (gpt-oss) |
| `ai/mcp_server.py` | L2 | optional MCP server wrapping `ai/tools.py` (not on runtime path) |
| `ai/skills/__init__.py`, `skills/registry.py`, `skills/text_synthesis.py` | L2 | `@skill` registry + the **deterministic** `summarize_symptoms` |

**Backend — persistence** (`backend/rcalibrary/persistence/`)
| `report_cache.py` (+ `__init__.py`) | L1 | file-based saved-report JSON cache (`ReportCache`) |

**Frontend**
| `frontend/js/report/report-customize.js` | L1 | picker / confirm modal / progress card / width snap |
| `frontend/js/report/report-ai-chat.js` | L2 | the multi-turn **AI chat modal** |

**Docs**
| `docs/10-panel-customization.md` | L1 | customizable-panels guide |
| `docs/11-ai-panel-builder.md` | L2/L3 | AI mode guide (this folder is the integration packet) |

**Tests** (all offline)
| `tests/unit/test_panel_library.py`, `tests/api/test_panel_customize.py` | L1 |
| `tests/unit/test_ai_panel.py`, `tests/api/test_ai_panel.py` | L2 |
| `tests/unit/test_ai_llm_engine.py` | L3 (LLM loop via `FakeLLMClient` + adapter parsing) |

---

## ⚠️ Shared files — additive edits (merge the block; see the patch for exact lines)

**`backend/rcalibrary/config.py`**
- L1: `report_cache_dir`, `report_cache_max_bytes`.
- L2: `ai_enabled` (default `True`), `ai_provider` (default `"simulated"`), `ai_max_turns`, `ai_session_ttl_s`.
- L3: `ai_base_url`, `ai_model`, `ai_api_key`, `ai_request_timeout`, `ai_temperature`.

**`backend/rcalibrary/deps.py`**
- L1: `get_report_cache()`. L2: `get_ai_panel_engine()` (simulated/disabled + `extensions` hook).
- L3: provider branch inside `get_ai_panel_engine()`:
  ```python
  if settings.ai_provider in ("openai", "local", "gpt-oss", "gpt_oss"):
      if not settings.ai_base_url:
          return DisabledAIEngine()
      from .ai.llm import OpenAICompatLLMClient
      client = OpenAICompatLLMClient(base_url=settings.ai_base_url, model=settings.ai_model,
          api_key=settings.ai_api_key, timeout=settings.ai_request_timeout, temperature=settings.ai_temperature)
      return LLMToolEngine(get_engine(), client, ttl_s=settings.ai_session_ttl_s, max_turns=settings.ai_max_turns)
  ```
  (import line: `from .ai.engine import AIPanelEngine, DisabledAIEngine, LLMToolEngine, SimulatedAIEngine`).

**`backend/rcalibrary/extensions.py`** — L2: `register_ai_engine(provider, factory)` /
`get_ai_engine_factory(provider)` + reset in `_reset()` (so a plugin can register a custom engine).

**`backend/rcalibrary/workflow/models.py`**
- L1: `PanelType` += `pie`, `flow`, `stat_group`; `PanelEncoding` += `labels/values/state/badge/detail/sub/alert`; `WorkflowStage`/`WorkflowInfo`; `TemplateMeta.workflow`; `LibraryPanel`; `Template.panel_library` + `_check_cross_refs` library validation + `library_panel_by_id`.
- L2: `TemplateMeta.ai_panels: bool = False`; **`LibraryPanel.requires_ai: bool = False`**.

**`backend/rcalibrary/workflow/engine.py`**
- L1: `run_panel(template, library_panel, raw_inputs, principal, input_group)` (merged-template trick).
- L2: add the `params: dict | None = None` arg — overlays onto the bundle's analysis-step `.params`:
  ```python
  bundle_steps = list(library_panel.analysis)
  if params:
      bundle_steps = [s.model_copy(update={"params": {**s.params, **params}}) for s in bundle_steps]
  # ...use bundle_steps when building the merged template...
  ```

**`backend/rcalibrary/workflow/report_builder.py`** — L1: `_fill_pie`, `_fill_stat_group`,
`_fill_stat` badge/detail, dispatch for `pie`/`stat_group`/`flow`, `_DEFAULT_WIDTH` entries.

**`backend/rcalibrary/workflow/loader.py`** — L1: `_check_analyzers` also walks
`panel_library[*].analysis` (so a template with unloaded library analyzers is skipped at
discovery, not 500 on add).

**`backend/rcalibrary/reporting/contract.py`** — L1: `PanelType` literal += `flow/pie/stat_group`;
`StatData.badge/detail/value_text`; `StatGroupData`; `PanelPayload.stat_group` (+ map types).

**`backend/rcalibrary/solutions/base.py`** — L1: `SolutionResult.from_cache: bool = False`.

**`backend/rcalibrary/api/routes_templates.py`**
- L1: `POST /panel` (run_panel), `POST /save`, `/run` cache load, `GET /templates/{id}` exposes `panel_library` + `ai_panels`.
- L2: implement `POST /panel/ai` (was 501) → `AIPanelResponse`; gate on `template.meta.ai_panels`; `run_in_threadpool(ai.chat, ...)`; **reject `requires_ai` panels in `POST /panel` with 400**.

**`backend/rcalibrary/api/schemas.py`** — L1: `PanelRequest`, `PanelResponse`,
`SaveReportBody`, `SaveResponse`, `PanelLibraryPreview`, `TemplateDetail.panel_library`/`ai_panels`.
L2: `AIPanelRequest`, `AIPanelResponse`, `PanelLibraryPreview.requires_ai`.

**`pyproject.toml` / `requirements.txt`** — L3: optional `[ai]` extra = `openai>=1.0` (+ `mcp>=1.2`
optional). No LangGraph/LangChain/Anthropic.

**`.gitignore`** — L1: ignore `/data/cache/`.

**Tests/config**: `tests/conftest.py` (L1: isolate `RCA_REPORT_CACHE_DIR` to a tmp dir),
`tests/api/test_run_endpoint.py` (L1: read header stats from the `stat_group`).

**In-repo framework docs** (additive prose — merge only if you maintain these):
`docs/04-authoring-templates.md` (L1/L2: `panel_library` + `requires_ai` + analyzer params),
`docs/07-building-use-cases.md` (L2: AI synthesis skills note),
`docs/09-usecase-handoff.md` (L1/L2: ownership rows for the AI surface).

**Frontend**
- `frontend/js/api/endpoints.js` — L1: `addPanel`/`saveReport`/`runTemplate(refresh)`; **L2: `aiPanelChat(id, body)`**.
- `frontend/js/report/report-view.js` — L1: always-editable `ReportController` (add-strips, save, drag/resize); **L2: `_addPanelAI(index)` on the `"__ai__"` branch**.
- `frontend/js/report/report-customize.js` (new, above) — **L2: `panelPicker` filters `requires_ai`**.
- `frontend/js/panels/{panel-charts.js (chart-host), panel-kpi.js (stat_group), registry.js (destroy/plotEl)}` — L1.
- `frontend/js/views/view-runner.js` — L1/L2: thread `library`/`aiPanels`/`inputs`/`inputGroup` into `renderReport`.
- `frontend/css/{components.css, panels.css}` — L1 (grid/one-per-row/picker/modal) + **L2 `.ai-chat*` block in components.css**.

---

## ✋ Diverged files — re-apply the *intent* (you rewrote these for real data)

**`usecases/netcare_voc.py`** — your version likely differs (real Snowflake analyzers).
Re-apply these *capabilities*, not the literal lines:
- **L2 param-aware timeseries (the core of test case A).** Add helpers so the call-volume /
  KPI series honor AI params without changing the `TimeseriesData` contract:
  - `_norm_gran(value)` → maps a granularity string to `daily|3h|hourly|None`.
  - `_resolve_default_gran(params)` → the chart's default granularity (AI choice else `daily`).
  - `_build_grids(first_start, now, params)` → per-granularity grids+windows; **honors
    `params["date_start"]`/`["date_end"]` (ISO) to clamp the window**, falls back on an
    inverted/garbage range.
  - `_build_volume_ts(usids, anchor_usid, volume, first_start, last_end, now, params)` →
    the call-volume `TimeseriesData` (per-USID series + aggregate), used by both Step 2 and
    the new panel. **Your real volume analyzer should call `_build_grids`/equivalent and
    read `ctx.params` for `date_start`/`date_end`/`granularity`.**
  - New analyzer **`voc_call_volume_trend(ctx)`** — reuses the main `call_volume` data +
    Step-2 `cluster_usids`, reads `ctx.params`, returns `summary["volume_ts"]`.
  - **L2** new analyzer **`voc_transcript_summary(ctx)`** + `_transcript_markdown(...)` —
    groups transcripts by cluster, calls the `summarize_symptoms` skill (deterministic),
    returns `summary["markdown"]` + a `table`. (Synthesis is deferred → keep the
    deterministic skill; do **not** wire your LLM here yet.)
  - **L1** (if you don't already have them) `voc_complaint_distribution`, `voc_rrc_kpi`.
- **Key principle:** analyzers read AI knobs from **`ctx.params`** (`date_start`,
  `date_end`, `granularity`); the engine puts them there via `run_panel(params=...)`. As
  long as your real analyzers read those keys, the AI routing works unchanged.

**`templates/ana.rca.netcare-voc-trend/template.yaml`** — merge into your (real-data) YAML:
- **L2:** `meta.ai_panels: true`.
- **L2:** two `panel_library` entries:
  - `call_volume_trend` — **no own `data_pull`** (reuses your main `call_volume` pull);
    `analysis: [{id: call_volume_panel, analyzer: voc_call_volume_trend, inputs: {dataset: <your call-volume pull id>}}]`;
    `panel: {type: timeseries, analysis_ref: call_volume_panel, overlay_ref: ticket_search, encoding: {value: volume_ts}}`.
  - `transcript_summary` — **`requires_ai: true`**; own `data_pull` for transcripts;
    `analysis: [{id: transcript_analysis, analyzer: voc_transcript_summary, inputs: {dataset: <transcripts pull>}}]`;
    `panel: {type: markdown, analysis_ref: transcript_analysis, encoding: {value: markdown}}`.
  - (L1, if missing) `complaint_pie`, `rrc_kpi`.
- ⚠️ Validation: a library bundle's `data_pull`/`analysis` ids must **not collide** with
  your main pull/step ids; `call_volume_trend` references a *main* pull id (allowed).

**`templates/ana.rca.netcare-voc-trend/IMPLEMENTATION.md`** — your version differs (real-
data notes). Re-apply / reference the new **"AI panel mode"** section (the two test cases,
the `ctx.params` contract, and the `# LLM AGENT:` skill-swap note) into your copy.

---

## 🗑 Demo-only — keep your real data (ignored; not in the patch except generators)
- `data/samples/ana.rca.netcare-voc-trend/voc_call_transcripts.csv`, `voc_complaints.csv`,
  `voc_ran_kpi.csv` (new) and churn in `voc_call_volume.csv`/`voc_tickets.csv`/`voc_trends.csv`
  (regenerated). `generate_dummy.py` edits document the dummy *contracts* (new columns:
  transcripts `usid, call_time, transcript_text`) — useful as a reference for your real
  source, but you keep real data.
