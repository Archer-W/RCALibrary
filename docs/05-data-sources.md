# 05 — Data sources

Templates reference **logical datasets** (and optional parameterized SQL), never
connection details. Which provider answers is a config decision, so the same
templates run against sample CSVs today and Snowflake later.

## The interface

`datasources/base.py`:
- `DataPullRequest` — `dataset`, optional `sql`, `params` (bind params), neutral
  `filters` (`column`/`op`/`value`), `limit`, `columns`, and `namespace`
  (sample-provider convenience = template id; real providers ignore it).
- `FetchResult` — wraps a pandas DataFrame (used by analyzers) and offers
  `to_records()` for JSON.
- `DataSource` — `fetch(request) -> FetchResult` and `health() -> dict`.

`DataSourceRegistry` holds providers by name and an **active** name from config
(`RCA_DATASOURCE`, default `sample`).

## Sample provider (default, ships now)

`SampleDataProvider` resolves `dataset=foo` (+ `namespace=tmpl`) to
`data/samples/tmpl/foo.csv`, then `data/samples/foo.csv`. It applies `filters`
generically, plus two documented param conventions: a param matching a column →
equality filter, and `lookback_hours` (with a parseable `ts` column) → keep the
trailing time window. Everything runs offline.

## Snowflake (Phase 2 — stub today)

`SnowflakeProvider.fetch` currently raises with a clear message; its docstring
specifies the planned mapping (`dataset` → fully-qualified view, or parameterized
`sql` with named bind params; `filters` → a parameterized WHERE clause; result via
`cursor.fetch_pandas_all()`).

**To enable later:**
1. `pip install snowflake-connector-python[pandas]` (already listed, commented, in
   `requirements.txt`).
2. Implement `SnowflakeProvider.fetch` (and read creds from settings).
3. Add `SNOWFLAKE_*` to `.env` and set `RCA_DATASOURCE=snowflake`.

No template, engine, analyzer, or UI changes are required — templates are
source-agnostic.
