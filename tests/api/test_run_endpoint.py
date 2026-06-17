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


def _voc_run(client, payload):
    r = client.post("/api/templates/ana.rca.netcare-voc-trend/run", json=payload)
    assert r.status_code == 200
    return {p["id"]: p for p in r.json()["report"]["panels"]}


def test_voc_trend_id_found(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"})
    assert "T-1001" in panels["trend_info"]["markdown"]
    # data-quality indicator is always present, with a color state
    assert panels["data_freshness"]["stat"]["state"] in ("good", "bad", "neutral")


def test_voc_trend_id_not_found(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-9999"}, "input_group": "trend_id"})
    assert "not found" in panels["trend_info"]["markdown"].lower()
    assert panels["data_freshness"]["stat"]["sub"]  # freshness still shown on not-found


def test_voc_usid_date_found(client):
    panels = _voc_run(
        client,
        {"inputs": {"usid": "0123456", "date": "2026-06-10", "search_neighbors": True}, "input_group": "usid_date"},
    )
    assert "T-1001" in panels["trend_info"]["markdown"]
    assert "0123456" in panels["trend_info"]["markdown"]


def test_l2_l3_placeholders(client):
    assert client.get("/api/l2/info").status_code == 200
    assert client.post("/api/l2/run", json={"problem": "x"}).status_code == 501
    assert client.get("/api/l3/info").status_code == 200
    assert client.post("/api/l3/session", json={"goal": "x"}).status_code == 501
