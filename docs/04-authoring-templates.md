# 04 — Authoring a fixed-workflow template

A template is **data, not code**: a folder under `templates/` with a
`template.yaml`. Drop one in and it appears in the UI automatically (the registry
discovers `templates/*/template.yaml` at startup and validates it).

## Steps

1. **Create the folder** using a dotted `{domain}.{subdomain}.{topic}` id
   (mirrors NetSkills), e.g. `templates/ran.handover-failure/`. RCA-flavoured
   templates conventionally live under `ana.rca.*`.
2. **Write `template.yaml`** (see the schema below).
3. **(Optional) add a custom analyzer** in
   `backend/rcalibrary/analyzers/builtins.py` (or a new module imported by the
   package) with the `@analyzer("name")` decorator, and reference it by name. The
   built-ins (`threshold_breach`, `zscore_anomaly`, `passthrough`) cover many
   cases with **zero Python**.
4. **Add sample data** under `data/samples/<id>/<dataset>.csv` so the template
   runs offline immediately.
5. Restart the server — the template appears under its **problem** (the UI is
   problem-first: users browse problems, then pick a template). Multiple
   templates that share `meta.problem.id` are grouped under the same problem.

## Schema

```yaml
meta:
  id: ana.rca.my-template          # must match the folder name
  name: "Human title"
  description: "One line."
  version: "0.1.0"
  solution_level: 1                # 1=fixed workflow (the badge/approach shown in the UI)
  tags: [demo]
  problem:                         # which RCA problem this template addresses
    id: ran.throughput-degradation # templates sharing this id group under one problem
    name: "RAN throughput degradation"
    description: "Subscriber-impacting throughput drop on a cell."
    domain: "RAN"

inputs:                            # rendered as the UI form
  - name: node_id                  # binding key, referenced as ${input.node_id}
    label: "Node ID"
    type: string                   # string|int|float|bool|enum|date|datetime
    required: true
    default: "node-001"
    help: "Shown under the field."
    validation: { pattern: "^node-[0-9]{3}$" }   # min/max/min_length/max_length/pattern/step
  # enum fields need: options: [{ value: a, label: "A" }, ...]

data_pulls:                        # source-agnostic data requests
  - id: latency_ts                 # dataset key (referenced by analysis + panels)
    source: null                   # omit -> active source (sample now, snowflake later)
    query:
      dataset: latency_timeseries  # logical name the provider resolves
      params: { node_id: "${input.node_id}", lookback_hours: "${input.lookback_hours}" }
      filters:
        - { column: node_id, op: eq, value: "${input.node_id}" }   # quote ${...} inside { }!
      limit: 5000
    columns: [ts, node_id, latency_ms]

analysis:                          # ordered steps
  - id: latency_breaches
    analyzer: threshold_breach     # a registered analyzer name
    inputs: { dataset: latency_ts }
    params: { column: latency_ms, op: gt, threshold: "${input.latency_slo_ms}", severity: high }
    on_error: fail                 # or skip

report:
  title: "My report"
  panels:                          # ordered; each binds to a dataset and/or analysis
    - { id: kpi, type: stat, title: "Breaches", analysis_ref: latency_breaches, encoding: { value: breach_count } }
    - id: chart
      type: line                   # line|bar|scatter|table|stat|fields|timeseries|heatmap|markdown
      title: "Latency"
      dataset: latency_ts
      analysis_ref: latency_breaches   # anomalies overlaid on this panel
      encoding: { x: ts, y: latency_ms }
      options: { x_title: Time, y_title: "Latency (ms)" }
```

### YAML gotcha
Interpolation tokens `${input.x}` contain `{`/`}`. Inside an **inline flow
mapping** `{ ... }` you must **quote** them (`value: "${input.x}"`); in block
style they can be unquoted. Tokens that are the whole value resolve to the typed
input (e.g. an int), not a string.

## Inputs: a flat list OR mutually-exclusive groups

Use `inputs:` for a single form. For *"start from one of N input sets"*, use
`input_groups:` instead — each is `{key, label, inputs: [...]}`. The UI shows a
selector, only the chosen set is submitted, and **its key arrives as
`${input._input_group}`** so analyzers can branch on the starting point. Fields
also accept `placeholder:` (greyed example text).

```yaml
input_groups:
  - key: trend_id
    label: "Trend ID"
    inputs:
      - { name: trend_id, label: "Trend ID", type: string, required: true, placeholder: "e.g. T-1001" }
  - key: usid_date
    label: "USID + Date"
    inputs:
      - { name: usid, label: "USID", type: string, required: true }
      - { name: date, label: "Date", type: date, required: true }
```

## Keeping leading-zero IDs intact

Numeric-looking IDs (USIDs, cell IDs) lose leading zeros if parsed as numbers.
List them under the pull's `query.string_columns: [usid, trend_id]` so the sample
provider reads them as strings (for Snowflake, type the column VARCHAR).

## Panel reference

Every panel: `{id, type, title, dataset?, analysis_ref?, encoding{}, options{},
width?, visible_when?, overlay_ref?}`. A panel reads from its `dataset`
(charts/table) and/or from its `analysis_ref` step's `AnalysisResult`.

| `type` | reads from | `encoding` keys | notes |
|---|---|---|---|
| `line` / `scatter` | dataset (+ `analysis_ref`) | `x`, `y`, `series?` | anomalies → markers; `hline` annotations → dashed threshold |
| `bar` | dataset | `x`, `y`, `series?` | grouped via `series` |
| `stat` | analysis `summary` | `value`, `state`, `sub`, `alert` (summary keys) | big value; `options.unit`; `state` colors it; `alert` = red badge |
| `table` | analysis `table` (else dataset) | `columns` (display labels) | a cell may be `{value, tone}` → colored badge; `summary["empty_notice"]` shows when empty |
| `fields` | `summary[encoding.value]` | `value` → `{items:[{label,value,state,sub}], notice}` | grid of labeled boxes; `state` tints a box |
| `timeseries` | `summary[encoding.value]` | `value` → a `TimeseriesData` object | interactive (client-side USID/granularity toggles); `overlay_ref` adds toggleable bands |
| `heatmap` | dataset | `x`, `y`, `value` | pivots the dataset |
| `markdown` | `summary[encoding.value]` or `options.text` | `value?` | basic `**bold**` + line breaks |

Widths default by type (`stat`→third; charts/`table`/`fields`/`timeseries`→full;
`bar`→half); override with `width: full|half|third`. Panels sharing a 12-col row
are rendered equal height.

### Color coding
- **`stat` value** and **`fields` box**: `state` ∈ `good | warn | bad | neutral`
  → green / orange / red / grey (`stat` reads it from the summary key named by
  `encoding.state`).
- **`table` cell badge**: a cell emitted as `{value, tone}` renders as a colored
  pill; `tone` ∈ `red | amber | green | blue | grey | purple`. Plain scalars are text.

### Conditional panels & cross-step overlays
- `visible_when: {ref: <analysis_id>, key: <summary_key>}` — render the panel only
  when that analysis summary key is truthy (e.g. gate later steps on Step 1's
  `found`, so the flow visibly terminates when nothing is found).
- `overlay_ref: <analysis_id>` — a `timeseries` panel pulls an overlay from
  another step's `summary["ticket_overlay"]` (used to toggle ticket bands onto a
  chart owned by an earlier step).

## Analyzer contract

```python
from rcalibrary.analyzers.registry import analyzer
from rcalibrary.analyzers.context import AnalysisContext, AnalysisResult

@analyzer("my_analyzer")
def my_analyzer(ctx: AnalysisContext) -> AnalysisResult:
    df = ctx.dataset            # primary pandas DataFrame (this step's `inputs.dataset`)
    p = ctx.params              # resolved params (with ${input.*} substituted)
    ctx.inputs                  # validated template inputs (incl. _input_group)
    ctx.results                 # {step_id: AnalysisResult} of EARLIER steps -> chain on them
    ctx.datasets                # {pull_id: DataFrame} for EVERY pull -> read >1 source
    return AnalysisResult(
        summary={"count": int(len(df))},          # scalars + structured objects (see below)
        anomalies=[{"index": 0, "column": "x", "value": 1.0, "severity": "high", "reason": "..."}],
        annotations=[{"type": "hline", "y": 100, "label": "threshold"}],  # plot overlays
        table=df.head(50).to_dict("records"),     # rows for `table` panels (cells may be {value,tone})
    )
```

`summary` feeds the non-chart panels via `encoding` keys: a `stat` reads
`encoding.value/state/sub/alert`; a `fields`/`timeseries`/`markdown` panel reads
the single object/text at `encoding.value`. `ctx.results` lets a step build on an
earlier one (e.g. read a confirmed entity), and `ctx.datasets` lets one analyzer
join multiple pulls — the engine runs `analysis` steps in order and passes both in.
