# Design — NetCare VoC Trend Triage, Step 2: Neighbor trend correlation

**Date:** 2026-06-18 · **Template:** `ana.rca.netcare-voc-trend` · **Solution level:** 1 (fixed workflow)

## Goal

After Step 1 confirms a valid trend, Step 2 retrieves the **care-call-volume
timeseries** for the searched USID and for **neighbor USIDs that have correlated
trends**, and presents:

1. A **correlated-trends table** (searched USID + correlated neighbors).
2. An **interactive call-volume timeseries** with per-USID toggles, a
   granularity/time-window switcher, and a deduplicated **aggregate** line.

Shown only when Step 1 found a trend; if not found, Step 2 does not render (the
flow terminates at Step 1).

## Ownership split

- **Structure agent (this repo):** template wiring, report panels, the
  `timeseries` frontend panel, dummy data, and a **working analyzer stub** that
  shapes data into the contract below so the UI is testable now.
- **Data agent:** replaces the stub's query + the aggregation/**dedup** logic
  behind the same contract (marked `# DATA AGENT:` in `usecases/netcare_voc.py`).

## Interactivity model (decided)

**Client-side, all data embedded.** One run returns all three granularities for
every correlated USID plus the aggregate; the browser toggles instantly with no
re-fetch. These are downsampled series (tens–low-hundreds of points each), so the
payload stays small. No new API plumbing.

## Framework extensions (reusable for Steps 3–6)

1. **Analyzer chaining** — `AnalysisContext.results: dict[str, AnalysisResult]`
   carries prior steps' results. Step 1 publishes an `anchor` dict in its summary
   (`{found, usid, trend_id, trend_start_time, trend_status, last_update_time}`);
   Step 2 reads `ctx.results["collect_trend"].summary`.
2. **Panel gating** — `PanelSpec.visible_when: {ref, key}`. `report_builder`
   omits the panel when `analysis_results[ref].summary.get(key)` is falsy. Step 2
   panels use `visible_when: {ref: collect_trend, key: found}`.
3. **`timeseries` panel type** + payload contract (below).

## Data contract

### Correlated-trends table (`table` panel)
Analyzer returns `AnalysisResult.table` — record dicts with these exact keys
(also the column order via `encoding.columns`); searched USID first (distance 0):

`Trend ID`, `USID`, `Trend start`, `Duration`, `Distance (km)`, `Location type`

### Timeseries (`timeseries` panel)
Analyzer returns, under a summary key (e.g. `volume_ts`), a structure validated
into `TimeseriesData`:

```
{
  "default_granularity": "daily",
  "granularities": [
    {"key": "daily",  "label": "Daily"},
    {"key": "3h",     "label": "3-hourly"},
    {"key": "hourly", "label": "Hourly"}
  ],
  "windows": {                         # x-axis range per granularity (ISO)
    "daily":  {"start": "...", "end": "..."},
    "3h":     {"start": "...", "end": "..."},
    "hourly": {"start": "...", "end": "..."}
  },
  "series": [
    {
      "usid": "0123456",
      "label": "0123456 (searched)",
      "role": "anchor",                # anchor | neighbor | aggregate
      "by_gran": {
        "daily":  {"x": [...iso...], "y": [...num...]},
        "3h":     {"x": [...], "y": [...]},
        "hourly": {"x": [...], "y": [...]}
      }
    },
    ... neighbors ...,
    {"usid": "__aggregate__", "label": "Aggregated (dedup)", "role": "aggregate", "by_gran": {...}}
  ],
  "y_title": "Care call volume"
}
```

### Granularity windows (from the trends in scope)
`first_trend_start` = min start across correlated trends (incl. anchor).
`last_trend_end` = max end; Active/Cooling trends are ongoing → treated as today;
Closed trends end at their `last_update_time` (proxy; data agent may use a real
end column).

| granularity | from | to |
|---|---|---|
| daily (default) | first_trend_start − 30d | max(today, last_trend_end + 15d) |
| 3-hourly | first_trend_start − 7d | max(today, last_trend_end + 3d) |
| hourly | first_trend_start − 3d | max(today, last_trend_end + 1d) |

## Frontend — `panel-timeseries.js` (stateful)

Control bar above a Plotly chart:
- **Granularity** segmented buttons (3); default `daily`.
- **USID checkboxes** (one per non-aggregate series; default all on).
- **Aggregated (dedup)** checkbox (default on).

State held in closures (`selectedGran`, `visibleUsids: Set`, `showAggregate`);
each change calls `Plotly.react` to redraw. Anchor = solid/thicker line,
neighbors = normal, aggregate = dashed. X-axis range set from `windows[gran]`.
Resize handled by the registry (`.js-plotly-plot`).

## Dummy data
- `voc_neighbors.csv` — keyed by `anchor_usid`: `trend_id, usid, trend_start_time,
  trend_end_time` (blank = ongoing), `trend_status, distance_km, location_type`.
- `voc_call_volume.csv` — hourly raw `usid, timestamp, call_volume`. The stub
  resamples to the three granularities/windows and builds the aggregate
  (placeholder dedup = capped sum across USIDs).

## Files
- backend: `analyzers/context.py`, `workflow/engine.py`, `workflow/models.py`,
  `reporting/contract.py`, `workflow/report_builder.py`
- `usecases/netcare_voc.py` (anchor in Step 1 summary; new `voc_neighbor_correlation`)
- template `template.yaml`; dummy CSVs + `generate_dummy.py`
- frontend: `panels/panel-timeseries.js` (new), `app.js`, `css/panels.css`
- tests: unit (windows, series shape, table, gating) + API (panels present when
  found / absent when not); `IMPLEMENTATION.md` Step-2 section + contract.

## Testing
- Unit: window math per granularity; series roles/aggregate present; table rows;
  gating flag. API: found → both panels present with granularities+series;
  not-found → both panels absent. Live HTTP + manual UI (toggle USIDs, switch
  granularity, aggregate line).
