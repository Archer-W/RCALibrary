# Template: `ana.rca.generic-demo`

A minimal, non-domain-specific template whose only job is to exercise the
Level-1 engine end to end: **inputs → data pull → analysis → report**.

- **Inputs:** `node_id`, `lookback_hours`, `latency_slo_ms`.
- **Data pulls:** `latency_timeseries` and `error_counts` from the sample
  provider (`data/samples/ana.rca.generic-demo/`).
- **Analysis:** `threshold_breach` (latency vs. SLO) and `zscore_anomaly`
  (error spikes).
- **Report:** two stat cards, a latency line chart (with anomaly markers + an
  SLO threshold line), an error bar chart, and a table of breaching samples.

The sample data deliberately contains an out-of-SLO latency window and an error
spike so anomaly highlighting is visible on every run.

To author a real template, copy this folder, rename it with a dotted
`{domain}.{subdomain}.{topic}` id, edit `template.yaml`, and drop matching CSVs
under `data/samples/<id>/`. See [`docs/04-authoring-templates.md`](../../docs/04-authoring-templates.md).
