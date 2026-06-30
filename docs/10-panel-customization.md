# 10 — Customizing a report (panel library, save/cache, AI chat)

A template's `report.panels` is the **default layout** — generic, good for most
scenarios, loaded on every run. For corner cases an operator can **customize** the
report at runtime: add less-common panels from a per-problem **library** (computed
on demand), remove panels, drag to reorder / snap-resize width, and **save** the
result so re-searching the same key reloads it without recompute.

This is a **generic framework feature** — any template gets it for free; the VoC
Trend Triage template just ships two example library panels to exercise it.

## What the user can do (always editable — no toggle)
The report is **directly editable**: every panel always shows its controls and an
"Add an RCA panel" strip sits between every row. The header has a **Save report**
button. Panels render **one per row** (a panel's width is a fraction of its own row).
- **Add** — click an "Add an RCA panel" strip between rows → pick one from the
  problem's library → it computes on demand (a progress bar shows) and is inserted.
- **Remove** — the panel's ✕ (a confirm dialog guards it).
- **Reorder** — drag the panel's ⠿ handle onto another panel.
- **Resize** — drag a panel's right edge; width snaps to third / half / full.
- **Save** — persists the current arrangement (added panels + order + widths +
  removals) under the search key.

Several stat cards can be **combined into one panel** with the `stat_group` panel
type (e.g. the VoC header row: freshness + likely-root-cause + PRT in one row);
each sub-stat in `options.stats` reads its own `analysis_ref` + summary keys and
may be gated with its own `visible_when`.

Re-searching the **same key** returns the saved report instantly (a *"Loaded a
saved report · Re-run fresh"* banner is shown); **Re-run fresh** recomputes.

## Panel library — `template.yaml` `panel_library`
Optional panels are **not** in `report.panels`; they live under a top-level
`panel_library`. Each entry is a **self-contained bundle**: its own (lazily-run)
`data_pulls` + `analysis`, and a `panel` (a normal `PanelSpec`). A bundle's
analysis may **chain on the main analysis** results via `ctx.results`.

```yaml
panel_library:
  - id: complaint_pie
    title: "Customer complaint type distribution"
    description: "Shown in the add-panel picker."
    data_pulls:
      - { id: complaints, query: { dataset: voc_complaints, string_columns: [usid] } }
    analysis:
      - { id: complaint_distribution, analyzer: voc_complaint_distribution, inputs: { dataset: complaints } }
    panel:
      id: complaint_pie
      type: pie
      title: "Customer complaint type distribution"
      analysis_ref: complaint_distribution
      encoding: { labels: complaint_type, values: count }
      options: { hole: 0.45 }
```

**Validation** (at template load): library ids are unique and must not clash with
`report.panels` ids; the bundle's `panel`/`analysis` refs resolve against the
**union** of main + bundle pulls/steps. A bundle is computed only when added.

### Ownership (see [09-usecase-handoff.md](09-usecase-handoff.md))
- **STRUCTURE agent** owns each bundle's `panel` (type/encoding/options/title) and
  whether it's offered.
- **DATA agent** owns each bundle's `data_pulls` + `analysis` (real query + logic),
  behind `# DATA AGENT:` markers in the analyzer.

## How on-demand compute works
`POST /api/templates/{id}/panel` `{panel_id, inputs, input_group}` →
`TemplateEngine.run_panel` runs the **main** pulls/analysis (so the panel can chain
on them) **plus** the bundle's own pulls/analysis over an ephemeral *merged*
template, then builds just that one panel and returns its `PanelPayload`. The
default `/run` never computes library panels.

## Save / cache
- `POST /api/templates/{id}/save` `{inputs, input_group, report}` stores the
  client-assembled report (a `ReportPayload`-shaped blob) under
  `key = sha256(template_id | input_group | inputs)` — a JSON file under
  `RCA_REPORT_CACHE_DIR` (default `data/cache/`). Stdlib only; inspect/clear by
  deleting files.
- `POST /api/templates/{id}/run`: if a saved blob exists for the key (and
  `refresh` is not set) it is returned with `from_cache: true`; a malformed/stale
  blob falls through to a fresh compute. `refresh: true` always recomputes.

## AI chat — build a panel from a description
When a template sets `meta.ai_panels: true`, the "Add panel" picker shows an
**"✨ Ask AI to build a panel"** option that opens a **multi-turn chat**. The AI
engine parses a free-text request, picks a predefined library panel, fills its
parameters (date range / granularity), and builds it — or asks a clarifying
question, or says it can't. It returns a `PanelPayload` via the **same** contract as
library panels, so AI-built panels compose with default + library panels.

This repo ships a **free, offline, deterministic** engine (no LLM, no API key, no
cost); the real LLM is connected by the other agent in its own environment via a
stable MCP tool server + engine interface. A library panel can be marked
**`requires_ai: true`** (e.g. a transcript text-summary) — hidden from the manual
picker and only buildable via the chat.

See **[11-ai-panel-builder.md](11-ai-panel-builder.md)** for the full design: the
`/panel/ai` chat protocol, panel parameters, skills, `RCA_AI_*` config, and how to
connect a real LLM.
