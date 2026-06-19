from datetime import datetime, timezone

import pandas as pd

from rcalibrary.analyzers.context import AnalysisContext, AnalysisResult
from usecases.netcare_voc import voc_ticket_search


def _tickets():
    return pd.DataFrame(
        [
            {"ticket_id": "T-A1", "anchor_usid": "A1", "usid": "A1", "dist_to_trend_km": 0.0, "ticket_type": "Outage", "event_name": "E1",
             "event_start_time": "2026-06-10T00:00:00Z", "event_end_time": "2026-06-10T02:00:00Z",
             "prt": "2026-06-10T03:00:00Z", "ticket_status": "open", "assoc_confidence": 0.9, "projected_impact": "High"},
            {"ticket_id": "T-A2", "anchor_usid": "A1", "usid": "A2", "dist_to_trend_km": 0.0, "ticket_type": "Maintenance", "event_name": "E2",
             "event_start_time": "2026-06-09T00:00:00Z", "event_end_time": "", "prt": "",
             "ticket_status": "closed", "assoc_confidence": 0.5, "projected_impact": "Low"},
            {"ticket_id": "T-A3", "anchor_usid": "A1", "usid": "A3", "dist_to_trend_km": 0.0, "ticket_type": "Alarm", "event_name": "E3",
             "event_start_time": "2026-06-08T00:00:00Z", "event_end_time": "", "prt": "",
             "ticket_status": "open", "assoc_confidence": 0.3, "projected_impact": "Medium"},
            # a 2-hop USID (NOT in the cluster) — distance comes from dist_to_trend_km
            {"ticket_id": "T-A9", "anchor_usid": "A1", "usid": "A9", "dist_to_trend_km": 5.0, "ticket_type": "Outage", "event_name": "E9",
             "event_start_time": "2026-06-07T00:00:00Z", "event_end_time": "", "prt": "",
             "ticket_status": "open", "assoc_confidence": 0.2, "projected_impact": "Medium"},
            # different anchor — must be excluded
            {"ticket_id": "T-Z9", "anchor_usid": "Z9", "usid": "Z9", "dist_to_trend_km": 0.0, "ticket_type": "Outage", "event_name": "X",
             "event_start_time": "2026-06-01T00:00:00Z", "event_end_time": "", "prt": "",
             "ticket_status": "open", "assoc_confidence": 0.99, "projected_impact": "High"},
        ]
    )


def _run(found=True, usid="A1", cluster=("A1", "A2", "A3"), cluster_active=True):
    results = {"collect_trend": AnalysisResult(summary={"found": found, "anchor": {"found": found, "usid": usid}})}
    if cluster is not None:
        results["neighbor_correlation"] = AnalysisResult(
            summary={"cluster_usids": list(cluster), "cluster_active": cluster_active}
        )
    ctx = AnalysisContext(dataset=_tickets(), params={}, inputs={}, results=results, datasets={})
    return voc_ticket_search(ctx)


def test_gated_out_when_no_anchor():
    res = _run(found=False)
    assert res.summary["found"] is False
    assert res.table == []


def test_only_cluster_tickets_ranked_by_confidence_desc():
    rows = _run().table
    assert [r["Confidence"]["value"] for r in rows] == ["90%", "50%", "30%", "20%"]  # desc
    assert all(r["Event name"] != "X" for r in rows)  # other anchor excluded


def test_color_tones_per_column():
    rows = _run().table
    assert rows[0]["Ticket type"] == {"value": "Outage", "tone": "red"}
    assert rows[0]["Status"]["tone"] == "amber"   # open
    assert rows[0]["Confidence"]["tone"] == "green"  # 0.9 >= 0.7
    assert rows[0]["Impact"]["tone"] == "red"     # High
    assert rows[1]["Ticket type"]["tone"] == "blue"   # Maintenance
    assert rows[1]["Status"]["tone"] == "grey"    # closed
    assert rows[1]["Confidence"]["tone"] == "amber"   # 0.5 in [0.4,0.7)
    assert rows[1]["Impact"]["tone"] == "green"   # Low
    assert rows[2]["Ticket type"]["tone"] == "amber"  # Alarm
    assert rows[2]["Confidence"]["tone"] == "grey"    # 0.3 < 0.4


def test_distance_to_trend_zero_in_cluster_else_km_color_coded():
    rows = {r["USID"]: r for r in _run().table}
    assert rows["A1"]["Trend dist (km)"] == {"value": "0", "tone": "green"}    # in cluster
    assert rows["A2"]["Trend dist (km)"] == {"value": "0", "tone": "green"}    # in cluster
    assert rows["A9"]["Trend dist (km)"] == {"value": "5.0", "tone": "amber"}  # 2-hop, <=5 km


def test_optional_times_render_dash_when_blank():
    rows = _run().table
    assert rows[1]["Event end"] == "—"
    assert rows[1]["PRT"] == "—"
    assert rows[0]["PRT"] != "—"  # present when set


def test_empty_cluster_returns_domain_notice():
    # anchor whose USID has no tickets -> empty table with a domain message
    res = _run(usid="NOPE", cluster=("NOPE",))
    assert res.table == []
    assert "no known network events" in res.summary["empty_notice"].lower()


def test_root_cause_and_prt_from_top_ticket():
    s = _run().summary
    assert s["rc_value"] == "90%" and s["rc_state"] == "good"  # top ticket T-A1 (0.9)
    assert s["rc_sub"] == "Outage · E1"
    assert s["prt_value"] != "missing"  # T-A1 has a PRT


def test_missing_prt_shows_missing():
    df = _tickets()
    df.loc[df["ticket_id"] == "T-A1", "prt"] = ""  # top ticket loses its PRT
    prior = AnalysisResult(summary={"found": True, "anchor": {"found": True, "usid": "A1"}})
    ctx = AnalysisContext(
        dataset=df, params={}, inputs={},
        results={"collect_trend": prior,
                 "neighbor_correlation": AnalysisResult(summary={"cluster_usids": ["A1", "A2", "A3"]})},
        datasets={},
    )
    s = voc_ticket_search(ctx).summary
    assert s["prt_value"] == "missing" and s["prt_state"] == "neutral"


def test_no_tickets_root_cause_not_identified():
    s = _run(usid="NOPE", cluster=("NOPE",)).summary
    assert s["rc_value"] == "—"            # no identifiable root cause
    assert s["prt_value"] == "missing"


def test_prt_expired_is_flagged():
    s = _run(cluster_active=False).summary  # top T-A1 PRT is 2026-06-10 -> past
    assert s["prt_state"] == "bad"
    assert "expired" in s["prt_sub"].lower()
    assert s["prt_alert"] is None  # no active cluster trend -> no escalation badge


def test_prt_alert_when_expired_and_cluster_active():
    s = _run(cluster_active=True).summary
    assert s["prt_state"] == "bad"
    assert s["prt_alert"] and "trend active" in s["prt_alert"].lower()  # prominent alert badge
    assert s["prt_sub"] is None  # the alert badge replaces the muted sub


def test_prt_future_is_not_expired():
    df = _tickets()
    future = (pd.Timestamp(datetime.now(timezone.utc)) + pd.Timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    df.loc[df["ticket_id"] == "T-A1", "prt"] = future  # top ticket PRT in the future
    prior = AnalysisResult(summary={"found": True, "anchor": {"found": True, "usid": "A1"}})
    ctx = AnalysisContext(
        dataset=df, params={}, inputs={},
        results={"collect_trend": prior,
                 "neighbor_correlation": AnalysisResult(summary={"cluster_usids": ["A1", "A2", "A3"], "cluster_active": True})},
        datasets={},
    )
    s = voc_ticket_search(ctx).summary
    assert s["prt_state"] == "neutral"
    assert "expired" not in s["prt_sub"].lower() and "alert" not in s["prt_sub"].lower()


def test_ticket_overlay_for_timeseries():
    ov = {o["id"]: o for o in _run().summary["ticket_overlay"]}
    assert set(ov) == {"T-A1", "T-A2", "T-A3", "T-A9"}  # ranked set, excl. other anchor
    top = ov["T-A1"]
    assert top["tone"] == "green"            # confidence-based color (0.9)
    assert top["start"] and top["end"]       # positioned window
    assert ov["T-A2"]["end"] is None         # ongoing (blank end)
    # structured fields the frontend composes into a color-coded tag (no time)
    assert top["usid"] == "A1" and top["type"] == "Outage"
    assert top["status"] == "open" and top["status_tone"] == "amber"
    assert top["impact"] == "High" and top["impact_tone"] == "red"
    assert top["event"] == "E1"
    assert "lines" not in top  # time-based lines removed
