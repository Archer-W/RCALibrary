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


def _field(panel, label):
    for item in panel["fields"]["items"]:
        if item["label"] == label:
            return item
    return None


def _stat(panels, title):
    # the 3 header stats are combined into one stat_group panel ("header_stats")
    for item in panels["header_stats"]["stat_group"]["items"]:
        if item["label"] == title:
            return item
    return None


def test_voc_trend_id_found(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"})
    # one box per value, including the new Duration box
    assert panels["trend_info"]["type"] == "fields"
    assert _field(panels["trend_info"], "Trend ID")["value"] == "T-1001"
    assert _field(panels["trend_info"], "Trend status")["state"] in ("good", "warn", "bad", "info", "neutral")
    assert "day" in _field(panels["trend_info"], "Duration")["value"].lower()
    # data-quality indicator is always present, with a color state
    assert _stat(panels, "Table data freshness")["state"] in ("good", "bad", "neutral")


def test_voc_trend_id_not_found(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-9999"}, "input_group": "trend_id"})
    assert panels["trend_info"]["fields"]["items"] == []
    assert "not found" in panels["trend_info"]["fields"]["notice"].lower()
    assert _stat(panels, "Table data freshness")["sub"]  # freshness still shown on not-found


def test_voc_usid_date_found(client):
    panels = _voc_run(
        client,
        {"inputs": {"usid": "0123456", "date": "2026-06-10", "search_neighbors": True}, "input_group": "usid_date"},
    )
    assert _field(panels["trend_info"], "Trend ID")["value"] == "T-1001"
    assert _field(panels["trend_info"], "USID")["value"] == "0123456"


def test_voc_step2_panels_present_when_found(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"})
    # Correlated-trends table: searched USID first, with the contract columns.
    nt = panels["neighbor_table"]["table"]
    assert nt["columns"] == ["Trend ID", "USID", "Trend status", "Trend start", "Duration", "Distance (km)", "Location type"]
    assert nt["rows"][0][0] == "T-1001" and nt["rows"][0][1] == "0123456"
    assert nt["rows"][0][2] == {"value": "Active", "tone": "red"}  # status badge
    # Interactive timeseries: 3 granularities + anchor/neighbor/aggregate series.
    ts = panels["neighbor_timeseries"]["timeseries"]
    assert [g["key"] for g in ts["granularities"]] == ["daily", "3h", "hourly"]
    roles = {s["role"] for s in ts["series"]}
    assert {"anchor", "neighbor", "aggregate"} <= roles
    anchor = next(s for s in ts["series"] if s["role"] == "anchor")
    assert anchor["usid"] == "0123456"
    pts = anchor["by_gran"]["daily"]
    assert len(pts["x"]) == len(pts["y"]) > 0
    # trend-span band (earliest start -> latest end) is provided for the shade
    assert ts["trend_span"]["start"] and ts["trend_span"]["end"]


def test_voc_triage_workflow_on_input_page(client):
    # the triage workflow is informational template meta (shown on the input page),
    # NOT a report panel
    r = client.get("/api/templates/ana.rca.netcare-voc-trend")
    assert r.status_code == 200
    wf = r.json()["meta"]["workflow"]
    assert wf and len(wf["stages"]) >= 6
    assert any(len(s["steps"]) > 1 for s in wf["stages"])  # has parallel stages
    # and it is NOT emitted as a report panel
    panels = _voc_run(client, {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"})
    assert "triage_flow" not in panels


def test_voc_root_cause_has_ticket_badge_and_event_detail(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"})
    rc = _stat(panels, "Likely root cause")
    assert rc["badge"] == "TKT-1001"          # ticket number, highlighted
    assert rc["detail"] and rc["detail"] != "—"  # event name shown prominently
    assert rc["state"] in ("good", "warn", "neutral")


def test_voc_map_panel(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"})
    m = panels["trend_map"]["map"]
    roles = {}
    for f in m["features"]:
        roles[f["role"]] = roles.get(f["role"], 0) + 1
    assert roles.get("cluster") and roles.get("neighbor")  # trend cluster + nearby no-trend sites
    anchor = next(f for f in m["features"] if f["usid"] == "0123456")
    assert anchor["color"] == "#c0392b"  # Active -> red
    assert any(f["color"] == "#0568AE" for f in m["features"])  # a Closed trend -> blue
    assert m["legend"] and m["center"]


def test_voc_trend_panel_has_call_total_boxes(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"})
    labels = [i["label"] for i in panels["trend_info"]["fields"]["items"]]
    assert "Calls on searched USID" in labels and "Cluster calls (dedup)" in labels
    # inserted right after the Trend status box (per the overlay after_label)
    assert labels.index("Calls on searched USID") == labels.index("Trend status") + 1


def test_voc_step2_gated_out_when_not_found(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-9999"}, "input_group": "trend_id"})
    assert "neighbor_table" not in panels
    assert "neighbor_timeseries" not in panels
    assert "ticket_table" not in panels  # Step 3 gated out too
    assert "trend_map" not in panels  # map gated out too


def test_voc_step3_ticket_table_present_and_ranked(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"})
    t = panels["ticket_table"]["table"]
    assert t["columns"] == [
        "Ticket ID", "Ticket type", "Event name", "USID", "Trend dist (km)",
        "Event start", "Event end", "PRT", "Status", "Confidence", "Impact"
    ]
    # ranked by confidence desc (Confidence is column index 9)
    confs = [int(row[9]["value"].rstrip("%")) for row in t["rows"]]
    assert confs == sorted(confs, reverse=True)
    # top ticket is the highest-confidence outage on the searched USID (in cluster -> 0, green)
    assert t["rows"][0][0] == "TKT-1001"
    assert t["rows"][0][1] == {"value": "Outage", "tone": "red"}
    assert t["rows"][0][3] == "0123456"
    assert t["rows"][0][4] == {"value": "0", "tone": "green"}  # in cluster -> green
    assert t["rows"][0][9]["tone"] == "green"  # high confidence
    # a 2-hop ticket carries a non-zero, color-coded distance to the trend
    backhaul = next(r for r in t["rows"] if r[2] == "Backhaul link flap")
    assert backhaul[3] == "0999003" and backhaul[4] == {"value": "9.5", "tone": "grey"}


def test_voc_root_cause_and_prt_boxes(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"})
    rc = _stat(panels, "Likely root cause")
    assert rc["value"] == "95%" and rc["state"] == "good"   # top ticket TKT-1001 (0.95)
    assert "Outage" in rc["sub"]
    prt = _stat(panels, "Planned restore (PRT)")
    assert prt["value"] != "missing"  # TKT-1001 has a PRT
    assert prt["state"] == "bad"  # PRT (Jun 11) is in the past -> expired
    assert prt["alert"] and "trend active" in prt["alert"].lower()  # prominent alert badge
    # the root-cause + PRT sub-stats are gated out when no trend is found
    nf = _voc_run(client, {"inputs": {"trend_id": "T-9999"}, "input_group": "trend_id"})
    assert _stat(nf, "Likely root cause") is None and _stat(nf, "Planned restore (PRT)") is None
    assert _stat(nf, "Table data freshness") is not None  # freshness still shown


def test_voc_timeseries_carries_ticket_overlay(client):
    panels = _voc_run(client, {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"})
    overlay = panels["neighbor_timeseries"]["timeseries"]["tickets"]
    assert len(overlay) == 8  # all tickets for this anchor, toggleable on the chart
    top = next(o for o in overlay if o["id"] == "TKT-1001")
    assert top["tone"] == "green" and top["start"]
    assert top["usid"] == "0123456" and top["type"] == "Outage"
    assert top["event"] == "Fiber cut – metro ring 12"


def test_l2_l3_placeholders(client):
    assert client.get("/api/l2/info").status_code == 200
    assert client.post("/api/l2/run", json={"problem": "x"}).status_code == 501
    assert client.get("/api/l3/info").status_code == 200
    assert client.post("/api/l3/session", json={"goal": "x"}).status_code == 501
