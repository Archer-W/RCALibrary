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


def test_voc_template_exposes_input_groups(client):
    d = client.get("/api/templates/ana.rca.netcare-voc-trend").json()
    # Incident ID set removed -> two sets remain.
    assert [g["key"] for g in d["input_groups"]] == ["trend_id", "usid_date"]
    usid_date = next(g for g in d["input_groups"] if g["key"] == "usid_date")
    assert [i["name"] for i in usid_date["inputs"]] == ["usid", "date", "search_neighbors"]
    # example placeholder + highlighted (**bold**) help on the first field
    trend = d["input_groups"][0]["inputs"][0]
    assert trend["placeholder"]
    assert "**USID-level**" in trend["help"]
    assert d["inputs"] == []  # grouped template has no flat inputs
