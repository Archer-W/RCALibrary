from rcalibrary.deps import get_engine, get_template_registry


def run_demo():
    registry = get_template_registry()
    engine = get_engine()
    template = registry.get("ana.rca.generic-demo")
    return engine.run(
        template,
        {"node_id": "node-001", "lookback_hours": 24, "latency_slo_ms": 120},
        None,
    )


def test_engine_assembles_report():
    report = run_demo().report
    assert report.template_id == "ana.rca.generic-demo"
    assert report.generated_at
    assert report.summary["total_anomalies"] >= 1


def test_line_panel_has_anomaly_overlay_and_threshold():
    report = run_demo().report
    line = next(p for p in report.panels if p.id == "latency_chart")
    assert line.type == "line"
    assert line.anomalies and len(line.anomalies.points) >= 1
    assert line.layout.get("shapes"), "expected a threshold shape on the line chart"


def test_stat_and_table_panels():
    report = run_demo().report
    stat = next(p for p in report.panels if p.id == "breach_count")
    assert stat.stat.value >= 1
    table = next(p for p in report.panels if p.id == "breach_table")
    assert table.table.columns == ["ts", "node_id", "latency_ms"]
    assert len(table.table.rows) >= 1
