VALID = {"node_id": "node-001", "lookback_hours": 24, "latency_slo_ms": 120}


def test_run_returns_report_with_anomalies(client):
    res = client.post("/api/templates/ana.rca.generic-demo/run", json={"inputs": VALID})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["report"]["summary"]["total_anomalies"] >= 1
    assert len(body["report"]["panels"]) == 5


def test_run_invalid_inputs_returns_422(client):
    bad = {**VALID, "node_id": "BAD"}
    res = client.post("/api/templates/ana.rca.generic-demo/run", json={"inputs": bad})
    assert res.status_code == 422
    assert "node_id" in res.json()["errors"]


def test_l2_l3_placeholders(client):
    assert client.get("/api/l2/info").status_code == 200
    assert client.post("/api/l2/run", json={"problem": "x"}).status_code == 501
    assert client.get("/api/l3/info").status_code == 200
    assert client.post("/api/l3/session", json={"goal": "x"}).status_code == 501
