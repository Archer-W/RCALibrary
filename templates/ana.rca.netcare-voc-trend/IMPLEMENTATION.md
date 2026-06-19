# IMPLEMENTATION — NetCare VoC Trend Triage

This template runs a fixed, ordered triage. **Steps 1–3 are implemented and run
against bundled dummy data.** This doc tells the **data agent** how to (A) point
it at real data, and (B) build the remaining steps.

Read first: [docs/07-building-use-cases.md](../../docs/07-building-use-cases.md),
[docs/05-data-sources.md](../../docs/05-data-sources.md).

## The fixed-workflow triage

1. **Trend look-up** — **IMPLEMENTED** (`voc_collect_trend`).
2. **Neighbor trend correlation** — **IMPLEMENTED** (`voc_neighbor_correlation`, stub data).
3. **Known network-event search & ranking** — **IMPLEMENTED** (`voc_ticket_search`, stub data).
4. Customer-complaint summary — TODO
5. Neighbor impact analysis — TODO
6. Conclusion & recommended next steps — TODO

## Inputs & the workflow starting point

The user picks ONE of two input sets; the chosen set's key arrives as
`${input._input_group}` (and in the audit event). Step 1 branches on it:

| `_input_group` | fields | Step 1 lookup |
|---|---|---|
| `trend_id` | `trend_id` (USID-level GSA/NetCare trend ID) | match the trend by its Trend ID |
| `usid_date` | `usid`, `date`, `search_neighbors` (bool) | match a trend on the USID within ±7 days of the date (closest) |

## What Step 1 does (already built)

- Logic: [`usecases/netcare_voc.py`](../../usecases/netcare_voc.py) → analyzer
  `voc_collect_trend` (loaded via `RCA_PLUGINS=usecases.netcare_voc`, set in `run.sh`).
- Output (report panels in `template.yaml`):
  - **Table data freshness** (always shown): delay of the table's latest
    `last_update_time` vs now; **red if > 6h, green otherwise** (a data-quality
    indicator), plus the table's last-update timestamp.
  - **Trend** (a `fields` panel — **one box per value**): if found, Trend ID,
    USID, **Trend status** (color-coded: **Active = red, Cooling = orange,
    Closed = grey**), trend start time, **Duration** (how long the trend has
    been there, in days), and last update time; if not found, a set-specific
    message and the flow stops (later steps will gate on `found`).
- Dummy data: [`data/samples/ana.rca.netcare-voc-trend/voc_trends.csv`](../../data/samples/ana.rca.netcare-voc-trend/voc_trends.csv),
  regenerate with `python data/samples/ana.rca.netcare-voc-trend/generate_dummy.py`
  (it stamps `last_update_time` ≈ now so freshness shows green; it turns red after 6h).

### Data contract (`voc_trends` dataset)
The analyzer + report expect these columns; **keep them when you wire real data**:

| column | meaning |
|---|---|
| `trend_id` | USID-level trend ID (string) |
| `usid` | cell tower ID (string — has leading zeros) |
| `trend_start_time` | trend start (ISO timestamp) |
| `trend_status` | **`Active` / `Cooling` / `Closed`** (case-insensitive; drives the status box color — red / orange / grey. Any other value renders grey) |
| `last_update_time` | row/table last refresh (ISO timestamp) — drives freshness |

**Duration** is *derived*, not stored: the analyzer computes whole days from
`trend_start_time` to now (or to that row's `last_update_time` for a `Closed`
trend, as a proxy for the close time). If your real source has a true close/end
timestamp, prefer it — adjust `_duration_str`'s `end_ref` in `netcare_voc.py`.

`voc_collect_trend` returns `summary`: `found`, `trend_fields` (a
`{items:[{label,value,state,sub}], notice}` structure rendered by the `fields`
panel — `state` is `good`/`warn`/`bad`/`neutral`), `delay_hours`, `delay_state`
(`good`/`bad`), `table_updated`.

## What Step 2 does (built as a STUB — you own the data logic)

Step 2 runs **only when Step 1 found a trend** (panels declare
`visible_when: {ref: collect_trend, key: found}`; otherwise the flow terminates
at Step 1). It reads Step 1's confirmed anchor via **analyzer chaining**
(`ctx.results["collect_trend"].summary["anchor"]` → `{usid, trend_id, ...}`) and
two data pulls. Output (panels in `template.yaml`):

- **Correlated trends** table — searched USID first (distance 0), then neighbor
  USIDs with correlated trends: `Trend ID · USID · Trend start · Duration ·
  Distance (km) · Location type`.
- **Care call volume** — an interactive `timeseries` panel: one line per USID
  (searched USID emphasized) + a dashed **Aggregated (dedup)** line. The user
  toggles USIDs on/off and switches **granularity**; all three granularities are
  embedded so toggling is **client-side, no re-fetch**.

The analyzer (`voc_neighbor_correlation`) is a **stub**: it shapes dummy data
into the contract so the UI works now. **You replace the marked `# DATA AGENT:`
spots** with the real query + dedup. The frontend/report need no changes.

### Granularity windows (computed in the analyzer, per these rules)
`first_trend_start` = earliest start among the correlated trends. The window
always **ends at now** (the x-axis is never in the future).

| granularity | from | to |
|---|---|---|
| daily *(default)* | first_trend_start − 30d | now |
| 3-hourly | first_trend_start − 7d | now |
| hourly | first_trend_start − 3d | now |

### Data contracts (Step 2 pulls)
`voc_neighbors` (correlated trends, **keyed by `anchor_usid`** so each searched
USID returns its own neighbor set):

| column | meaning |
|---|---|
| `anchor_usid` | the searched USID this row is a correlation for (string) |
| `trend_id`, `usid` | the correlated trend + its USID (strings) |
| `trend_start_time` | trend start (ISO) |
| `trend_end_time` | trend end (ISO); **blank = ongoing** |
| `trend_status` | Active / Cooling / Closed |
| `distance_km` | distance to the searched USID (0 for the anchor itself) |
| `location_type` | urban / suburban / rural / … |

`voc_call_volume` (per-USID care-call volume the analyzer resamples):

| column | meaning |
|---|---|
| `usid` | cell tower ID (string — leading zeros) |
| `timestamp` | sample time (ISO; dummy is hourly) |
| `call_volume` | calls in that bin (numeric) |

`voc_neighbor_correlation` returns `summary.found`, `summary.volume_ts`
(`TimeseriesData`: `granularities`, `windows`, `series[{usid,label,role,by_gran}]`,
`y_title`), and the table rows in `AnalysisResult.table`.

### Where you plug in (`# DATA AGENT:` in `netcare_voc.py`)
1. **Correlated-neighbor query** — replace the dummy `anchor_usid` filter with a
   real correlation query (geo neighbors with co-occurring trends), keyed by the
   anchor USID + time, honoring `search_neighbors`. **Cap to the top-N closest**
   neighbors (the rows are already sorted by `distance_km`): the chart palette
   has 8 categorical hues, and >8 simultaneous lines is hard to read anyway.
2. **Aggregate dedup** — `NEIGHBOR_DEDUP_FACTOR` is a placeholder (a capped sum).
   Real dedup is **record-level**: a call linked to >1 trend is counted once.
   Produce the deduped aggregate series and keep the `role: "aggregate"` series.
3. Resampling to daily/3h/hourly is generic; keep it or push it into SQL.

Two framework seams Step 2 added (reusable for Steps 3–6): `ctx.results` (prior
steps' results) and `ctx.datasets` (every pulled frame, so a step can read more
than one source).

## What Step 3 does (built as a STUB — you own the data logic)

Step 3 lists **tickets / known network events associated to the trend cluster**
— each cluster USID (Step 2) *and their 2-hop topology neighbors* — ranked by
**association confidence (desc)**. Gated on Step 1 `found`. Output is one
color-coded `table` panel (`ticket_table`) with columns:

`Ticket ID · Ticket type · Event name · USID · Trend dist (km) · Event start · Event end · PRT · Status · Confidence · Impact`

Tickets can also be **overlaid on the Step-2 call-volume chart**: the timeseries
panel declares `overlay_ref: ticket_search`, so it reads `ticket_search`'s
`ticket_overlay` (id, confidence tone, start/end, and structured fields: usid,
type, dist, status, impact, event + their tones). They're off by default;
clicking a ticket-ID chip draws a confidence-colored band over the event window
plus a colorful tag (USID · type / id / dist · status · impact / event name).

**Trend dist (km)** is 0 when the ticket's USID is in the trend cluster (Step 2's
`cluster_usids`), else the distance from that USID to the nearest cluster USID.
Color-coded: 0 km green · ≤5 km amber · >5 km grey.

Color-coding (the `table` panel renders a cell that is a `{value, tone}` object
as a colored badge — tones `red/amber/green/blue/grey/purple`):

| column | coding |
|---|---|
| Ticket type | categorical: outage=red, maintenance=blue, alarm=amber, congestion=purple, other=grey |
| Status | open=amber, closed=grey |
| Confidence | ≥0.7 green, 0.4–0.7 amber, <0.4 grey (shown as %) |
| Impact | high=red, medium=amber, low=green |

Two **header stat boxes** (next to "Table data freshness") summarize the top
(highest-confidence) ticket: **Likely root cause** (confidence %, colored by
confidence; type · event in the sub) and **Planned restore (PRT)** (the top
ticket's PRT, or "missing"). The PRT box turns **red when the PRT is in the past
(expired)**, and shows a **prominent pulsing red alert badge** when it is expired
*and* a cluster trend is still Active (`cluster_active`, published by Step 2 —
the anchor's own status counts even if the neighbors query returns no rows). Both
boxes come from `ticket_search`'s summary (`rc_*`, `prt_*` incl. `prt_alert`).

Logic: `voc_ticket_search` in [`usecases/netcare_voc.py`](../../usecases/netcare_voc.py).
It reads Step 1's anchor + Step 2's `cluster_usids` (chaining via `ctx.results`)
and the `tickets` pull (`ctx.dataset`). The badge cell shape (`{value, tone}`)
is generic — reuse it in any `table` panel.

### Data contract (`voc_tickets` pull, keyed by `anchor_usid` in the dummy)
| column | meaning |
|---|---|
| `ticket_id` | ticket/event identifier (string; shown in the table + the chart's toggle chips) |
| `anchor_usid` | the searched USID this ticket is associated to (string; dummy keying) |
| `usid`, `hop` | the USID the ticket is on + hop distance (0/1/2) from the searched USID |
| `dist_to_trend_km` | distance from the ticket USID to the nearest trend-cluster USID (0 for cluster members) |
| `ticket_type` | Outage / Maintenance / Alarm / Congestion / … |
| `event_name` | the event/ticket title |
| `event_start_time`, `event_end_time` | ISO; end blank = ongoing |
| `prt` | planned restore time (ISO; blank = n/a) |
| `ticket_status` | open / closed |
| `assoc_confidence` | association confidence in [0,1] (drives ranking + color) |
| `projected_impact` | High / Medium / Low |

### Where you plug in (`# DATA AGENT:` in `netcare_voc.py`)
1. **Scope** — expand Step 2's `cluster_usids` to their **2-hop topology
   neighbors** (your graph query) and gather the full USID set.
2. **Ticket query + confidence** — fetch tickets for those USIDs and compute the
   real **association confidence** (the dummy reads a column). Return the contract
   columns above; the analyzer's ranking + color-coding stay unchanged.

## (A) Switch from dummy data to real Snowflake — the main task

You change the **data source only**; the analyzer/report stay as-is.

1. **Implement a Snowflake `DataSource`** (provider name `snowflake`) as a plugin
   and register it — see [docs/07 §3 + §6](../../docs/07-building-use-cases.md).
   Use named bind params; never string-concatenate SQL.
2. **Point the pull at it.** In `template.yaml`, the `trends` data pull omits
   `source` (uses the active source). Either set `RCA_DATASOURCE=snowflake`, or
   add `source: snowflake` to the pull.
3. **Filter in SQL by input set.** The dummy pull fetches the whole small table
   and the analyzer filters. For real data, branch the query on
   `${input._input_group}` so it returns only the relevant trend(s):
   - `trend_id` → `WHERE trend_id = %(trend_id)s` against the **USID Trend table**.
   - `usid_date` → `WHERE usid = %(usid)s` near `%(date)s` against the **Trend
     table** (and honor `search_neighbors`).
   Add the needed params to the pull's `query.params` (e.g. `trend_id`, `usid`,
   `date`, `search_neighbors`, `input_group: "${input._input_group}"`).
4. **Return the contract columns** above (alias your real columns to these names),
   so `voc_collect_trend` and the report keep working unchanged. Keep `usid` (and
   any leading-zero IDs) as strings — for the sample provider that's
   `query.string_columns`; for Snowflake, ensure the column type is VARCHAR.

No changes to the analyzer or the report are required if the contract holds.

## (B) Build steps 4–6
Each step = data pull(s) + an analyzer (plugin) + report panel(s), gated on Step
1's `found` (use `visible_when`). Chain on earlier steps via `ctx.results` and
read extra sources via `ctx.datasets`. Coordinate report-panel additions with the
structure agent. Follow the `voc_collect_trend` / `voc_neighbor_correlation` /
`voc_ticket_search` patterns in `usecases/netcare_voc.py`.

## Verify
```bash
./run.sh    # loads the plugin + dummy data
# UI: NetCare VoC Trend Triage -> Fixed Workflow -> pick a set:
#   Trend ID = T-1001 (found) -> freshness + root-cause + PRT boxes,
#       trend boxes, neighbor table, call-volume timeseries, ticket table
#   Trend ID = T-9999 (not found) -> Step 2 & 3 panels do NOT render
#   USID = 0123456, Date = 2026-06-10 (-> T-1001)
# Timeseries: toggle USIDs, switch Daily/3-hourly/Hourly, toggle Aggregated,
#   click a ticket-ID chip to overlay its band + tag.
# PRT box: red "expired" when PRT < now; pulsing ⚠️ alert when expired + a trend is Active.
pytest      # unit + API tests for Steps 1–3
```
