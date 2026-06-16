# IMPLEMENTATION — NetCare VoC Trend Triage (for the data agent)

This template's **structure is done** (problem, inputs, report layout). Your job
is the **data-related work**: connect Snowflake and implement the analysis. You
do this **without changing the structure blocks** — coordinate first if you need
an input or panel that doesn't exist.

Read first: [docs/07-building-use-cases.md](../../docs/07-building-use-cases.md)
(how to extend the framework via plugins), [docs/05-data-sources.md](../../docs/05-data-sources.md),
and [docs/09-usecase-handoff.md](../../docs/09-usecase-handoff.md) (the ownership split).

## The fixed-workflow triage (the process to implement)

This template runs a fixed, ordered triage. Implement these as the `data_pulls` +
`analysis` steps (structure first, real data later):

1. **Trend look-up** — pull and characterize the VoC trend over the window.
2. **Neighbor trend correlation** — compare against neighboring entities/areas.
3. **Customer-complaint summary** — summarize the complaints driving the trend.
4. **Known network-event search & ranking** — find and rank related known events.
5. **Neighbor impact analysis** — assess impact on neighbors.
6. **Conclusion & recommended next steps** — synthesize a result.

Each step maps to one (or more) data pull(s) + analyzer(s), surfaced by report
panel(s). The current panels (volume/breakdown) are provisional placeholders; the
structure agent will reshape the report to the steps as they're defined —
coordinate panel changes. Below is the contract for the placeholders shipping now.

## Inputs & the workflow starting point

The user picks ONE of three mutually-exclusive input sets; the chosen set's key
arrives as `${input._input_group}` (and in the audit event). **Branch the
workflow's starting point on it** (exact logic TBD):

| `_input_group` | fields | start the workflow from… |
|---|---|---|
| `trend_id` | `trend_id` (USID-level GSA/NetCare trend ID) | the given trend |
| `usid_date` | `usid`, `date`, `search_neighbors` (bool) | look up trend(s) for the USID near the date; optionally search neighbors |
| `incident_id` | `incident_id` (USID-Cluster-level VoC incident ID) | the given incident |

Only the chosen set's fields are populated in `${input.*}`; the others resolve to
empty. Your data-pull SQL / analyzers should switch on `_input_group`.

## What you own in `template.yaml`
- the `data_pulls:` block (real Snowflake datasets / SQL / params / filters)
- the `analysis:` block (swap `passthrough` for your real analyzer names + params)

Do **not** edit `meta`, `inputs`, or `report` structure without coordinating with
the structure agent. You *will* need to update two `report` fields once your
analyzers exist — those are called out as "coordinate" below.

## The contract (keep these stable so the report keeps working)

| data_pull `id` | columns the report expects | meaning |
|---|---|---|
| `voc_volume` | `date`, `complaint_count` | VoC complaint volume per day over the window |
| `voc_breakdown` | `category`, `complaint_count` | complaint counts grouped by category |

| analysis `id` | bound dataset | the report consumes… |
|---|---|---|
| `volume_trend` | `voc_volume` | `summary` — a **dict**; the KPI panel reads the key named by `report.volume_kpi.encoding.value` (rename it from `row_count` to your key, e.g. `total_complaints`). Plus `anomalies` (markers on the line chart) and optional `annotations` (e.g. a baseline line). |
| `breakdown_summary` | `voc_breakdown` | **must return `table`** — the Top-drivers panel has no dataset fallback, so an analyzer that returns only `summary` renders an empty table. `summary` is optional. |

If you change a `data_pull` id/columns or an analysis id, update the matching
`report` panel `dataset`/`analysis_ref`/`encoding` **with the structure agent**.

## Step 1 — Snowflake data source (plugin)
Implement a `DataSource` named `snowflake` and register it; set
`RCA_DATASOURCE=snowflake`. Copy the framework stub
[`datasources/snowflake.py`](../../backend/rcalibrary/datasources/snowflake.py) as
a starting point (don't edit it in place — it's framework-owned). Pattern + the
`register_datasource(...)` call: [docs/07 §3 + §6](../../docs/07-building-use-cases.md).
Use **named bind params** from `request.params` — never string-concatenate SQL.

## Step 2 — Real queries (the `data_pulls` block)
For each pull, map `query.dataset` to a real view/table (or replace with `sql:`),
and wire `params`/`filters` to the inputs `start_date`, `end_date`, `region`,
`product_line`. Ensure the returned columns match the contract table above
(`voc_volume` → `date,complaint_count`; `voc_breakdown` → `category,complaint_count`).

## Step 3 — Analyzers (plugin) + the `analysis` block
Implement analyzers with `@analyzer("name")` in your plugin (loaded via
`RCA_PLUGINS`), then point the `analysis` block at them. Suggested:

```python
from rcalibrary.analyzers import analyzer
from rcalibrary.analyzers.context import AnalysisContext, AnalysisResult

@analyzer("voc_trend_anomaly")
def voc_trend_anomaly(ctx: AnalysisContext) -> AnalysisResult:
    df = ctx.dataset                       # columns: date, complaint_count
    # TODO: baseline + spike detection over complaint_count
    return AnalysisResult(
        summary={"total_complaints": int(df["complaint_count"].sum())},
        anomalies=[...],                   # {index,column,value,severity,reason} -> chart markers
        annotations=[{"type": "hline", "y": baseline, "label": "baseline"}],
    )

@analyzer("voc_top_drivers")
def voc_top_drivers(ctx: AnalysisContext) -> AnalysisResult:
    df = ctx.dataset                       # columns: category, complaint_count
    top = df.sort_values("complaint_count", ascending=False).head(10)
    return AnalysisResult(summary={"categories": int(len(df))}, table=top.to_dict("records"))
```

Then in `template.yaml`:
- `volume_trend.analyzer: voc_trend_anomaly` (+ any `params` like baseline window/threshold)
- `breakdown_summary.analyzer: voc_top_drivers`

**Coordinate change:** update `report.volume_kpi.encoding.value` from `row_count`
to your real summary key (e.g. `total_complaints`).

> Resilience note: if you reference an analyzer that isn't loaded (plugin not on
> `RCA_PLUGINS`), the framework **skips this template with a warning** instead of
> crashing — so keep your plugin loaded in every deployment that ships this template.

## Step 4 — Verify
```bash
RCA_DATASOURCE=snowflake RCA_PLUGINS=<your.plugins> pytest        # add a test
# or run the app and exercise the problem in the UI:
#   Problems -> "NetCare VoC Trend Triage" -> the template -> fill window -> Run
```
Acceptance:
- `GET /api/problems` lists `netcare.voc-trend` with this template.
- `POST /api/templates/ana.rca.netcare-voc-trend/run` returns a report whose line
  chart shows volume (with anomaly markers when a spike exists), the bar chart
  shows the category breakdown, the KPI shows the real metric, and the table
  lists top drivers.
