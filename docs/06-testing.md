# 06 — Testing

```bash
pip install -r requirements.txt
pytest
```

`pyproject.toml` sets `pythonpath = ["backend"]`, so `rcalibrary` imports without
installation, and `testpaths = ["tests"]`.

## What's covered

- **unit/**
  - `test_template_loader` — the demo template parses; discovery is deterministic.
  - `test_template_validation` — valid fixture loads; invalid fixtures (unknown
    analyzer, bad dataset ref, enum without options) raise `TemplateValidationError`.
  - `test_analyzers` — `threshold_breach`, `zscore_anomaly`, `passthrough`,
    including a missing-column error.
  - `test_sample_datasource` — filtering, projection, and missing-dataset error.
  - `test_report_assembly` — full engine run produces a report with anomaly
    overlays, a threshold shape, stat values, and table rows.
  - `test_solution_registry` — three levels with correct availability; L2/L3
    return `not_implemented` without raising.
- **api/** (FastAPI `TestClient`) — `/api/solutions`, template list/detail/404,
  run (200 + anomalies, 422 on bad input), and L2/L3 placeholders (501).
- **e2e/** — `test_end_to_end` walks the whole API path used by the UI.

## Manual UI verification (end-to-end recipe)

1. `./run.sh` (uvicorn, `RCA_DATASOURCE=sample`).
2. Open <http://localhost:8000/>.
3. Confirm the landing page lists **problems** (the **Generic Demo Problem**).
4. Open it and confirm the **Generic Demo RCA** template appears, badged
   *Fixed Workflow* / *Available*.
5. Click it, submit the default inputs (`node-001`, 24h, SLO 120).
6. Confirm the report renders: two KPI cards, a **latency line chart with red
   anomaly markers and a dashed SLO threshold line**, an error bar chart, and a
   table of breaching samples; the banner reports the anomaly count.
7. Confirm **About approaches** shows the three approach types + decision tree.

The sample data deliberately contains an out-of-SLO latency window and an error
spike, so anomaly highlighting appears on every run.
