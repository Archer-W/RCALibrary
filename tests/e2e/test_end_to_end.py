"""End-to-end happy path over the API (mirrors the manual UI recipe in docs/06)."""


def test_full_flow(client):
    # 1. Solutions: L1 available, L2/L3 coming soon.
    solutions = client.get("/api/solutions").json()
    assert solutions[0]["status"] == "available"
    assert all(s["status"] == "coming_soon" for s in solutions[1:])

    # 2. The demo template is listed.
    assert any(t["id"] == "ana.rca.generic-demo" for t in client.get("/api/templates").json())

    # 3. Its input schema is returned for form rendering.
    schema = client.get("/api/templates/ana.rca.generic-demo").json()
    assert {i["name"] for i in schema["inputs"]} >= {"node_id", "lookback_hours", "latency_slo_ms"}

    # 4. Run with inputs that hit the seeded anomaly.
    report = client.post(
        "/api/templates/ana.rca.generic-demo/run",
        json={"inputs": {"node_id": "node-001", "lookback_hours": 24, "latency_slo_ms": 120}},
    ).json()["report"]

    # 5. The report highlights anomalies on the chart + lists breaching rows.
    assert report["summary"]["total_anomalies"] >= 1
    line = next(p for p in report["panels"] if p["id"] == "latency_chart")
    assert len(line["anomalies"]["points"]) >= 1
    assert line["layout"].get("shapes")  # SLO threshold line
    table = next(p for p in report["panels"] if p["id"] == "breach_table")
    assert len(table["table"]["rows"]) >= 1
