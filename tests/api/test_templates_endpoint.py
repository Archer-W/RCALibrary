def test_list_templates_includes_demo(client):
    templates = client.get("/api/templates").json()
    assert any(t["id"] == "ana.rca.generic-demo" for t in templates)


def test_template_detail_returns_input_schema(client):
    res = client.get("/api/templates/ana.rca.generic-demo")
    assert res.status_code == 200
    body = res.json()
    names = {i["name"] for i in body["inputs"]}
    assert {"node_id", "lookback_hours", "latency_slo_ms"} <= names
    assert len(body["report_preview"]) == 5


def test_unknown_template_returns_404(client):
    assert client.get("/api/templates/does-not-exist").status_code == 404
