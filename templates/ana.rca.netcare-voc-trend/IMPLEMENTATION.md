# IMPLEMENTATION — NetCare VoC Trend Triage

This template runs a fixed, ordered triage. **Step 1 (collect trend information)
is implemented and runs against bundled dummy data.** This doc tells the **data
agent** how to (A) point it at real data, and (B) build the remaining steps.

Read first: [docs/07-building-use-cases.md](../../docs/07-building-use-cases.md),
[docs/05-data-sources.md](../../docs/05-data-sources.md).

## The fixed-workflow triage

1. **Trend look-up** — **IMPLEMENTED** (`voc_collect_trend`).
2. Neighbor trend correlation — TODO
3. Customer-complaint summary — TODO
4. Known network-event search & ranking — TODO
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
  - **Trend**: if found, Trend ID / USID / start time / status / last update; if
    not found, a set-specific message and the flow stops (later steps will gate
    on `found`).
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
| `trend_status` | e.g. open / monitoring / resolved |
| `last_update_time` | row/table last refresh (ISO timestamp) — drives freshness |

`voc_collect_trend` returns `summary`: `found`, `trend_md`, `delay_hours`,
`delay_state` (`good`/`bad`), `table_updated`.

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

## (B) Build steps 2–6
Each step = data pull(s) + an analyzer (plugin) + report panel(s), gated on Step
1's `found`. Coordinate report-panel additions with the structure agent. Follow
the `voc_collect_trend` pattern in `usecases/netcare_voc.py`.

## Verify
```bash
./run.sh    # loads the plugin + dummy data
# UI: NetCare VoC Trend Triage -> Fixed Workflow -> pick a set:
#   Trend ID = T-1001  (found) / T-9999 (not found)
#   USID = 0123456, Date = 2026-06-10  (-> T-1001)
pytest      # unit + API tests for Step 1
```
