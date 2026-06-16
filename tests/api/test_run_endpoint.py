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


def test_voc_requires_input_group(client):
    # grouped template: omitting input_group fails validation
    r = client.post("/api/templates/ana.rca.netcare-voc-trend/run", json={"inputs": {"trend_id": "GSA-1"}})
    assert r.status_code == 422


def test_voc_unknown_input_group(client):
    r = client.post(
        "/api/templates/ana.rca.netcare-voc-trend/run",
        json={"inputs": {}, "input_group": "nope"},
    )
    assert r.status_code == 422


def test_voc_valid_group_passes_validation_then_hits_snowflake(client):
    # A valid set + value passes validation, then errors at the Snowflake stub (502).
    r = client.post(
        "/api/templates/ana.rca.netcare-voc-trend/run",
        json={"inputs": {"trend_id": "GSA-1"}, "input_group": "trend_id"},
    )
    assert r.status_code == 502


def test_l2_l3_placeholders(client):
    assert client.get("/api/l2/info").status_code == 200
    assert client.post("/api/l2/run", json={"problem": "x"}).status_code == 501
    assert client.get("/api/l3/info").status_code == 200
    assert client.post("/api/l3/session", json={"goal": "x"}).status_code == 501
