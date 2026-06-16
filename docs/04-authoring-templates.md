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
      type: line                   # line|bar|scatter|table|stat|heatmap|markdown
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

## Analyzer contract

```python
from rcalibrary.analyzers.registry import analyzer
from rcalibrary.analyzers.context import AnalysisContext, AnalysisResult

@analyzer("my_analyzer")
def my_analyzer(ctx: AnalysisContext) -> AnalysisResult:
    df = ctx.dataset            # pandas DataFrame for the bound dataset
    p = ctx.params              # resolved params (with ${input.*} substituted)
    return AnalysisResult(
        summary={"count": int(len(df))},          # scalars for `stat` panels
        anomalies=[{"index": 0, "column": "x", "value": 1.0, "severity": "high", "reason": "..."}],
        annotations=[{"type": "hline", "y": 100, "label": "threshold"}],  # plot overlays
        table=df.head(50).to_dict("records"),     # rows for `table` panels
    )
```
