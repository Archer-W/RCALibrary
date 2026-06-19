import pandas as pd

from rcalibrary.analyzers.context import AnalysisContext, AnalysisResult
from usecases.netcare_voc import voc_neighbor_correlation


def _neighbors():
    return pd.DataFrame(
        [
            # anchor A1: its own trend (distance 0) + one neighbor
            {"anchor_usid": "A1", "trend_id": "T1", "usid": "A1", "trend_start_time": "2026-06-05T00:00:00Z",
             "trend_end_time": "", "trend_status": "Active", "distance_km": 0.0, "location_type": "urban"},
            {"anchor_usid": "A1", "trend_id": "N1", "usid": "A2", "trend_start_time": "2026-06-08T00:00:00Z",
             "trend_end_time": "", "trend_status": "Active", "distance_km": 1.0, "location_type": "suburban"},
            # a different anchor — must be filtered out
            {"anchor_usid": "Z9", "trend_id": "X9", "usid": "Z9", "trend_start_time": "2026-06-01T00:00:00Z",
             "trend_end_time": "", "trend_status": "Active", "distance_km": 0.0, "location_type": "rural"},
        ]
    )


def _volume():
    idx = pd.date_range("2026-06-01T00:00:00Z", "2026-06-15T00:00:00Z", freq="h")
    rows = []
    for usid in ("A1", "A2"):
        for t in idx:
            rows.append({"usid": usid, "timestamp": t.isoformat(), "call_volume": 10})
    return pd.DataFrame(rows)


def _run(anchor_found=True, anchor_usid="A1"):
    prior = AnalysisResult(summary={"found": anchor_found, "anchor": {"found": anchor_found, "usid": anchor_usid}})
    ctx = AnalysisContext(
        dataset=_neighbors(),
        params={},
        inputs={},
        results={"collect_trend": prior},
        datasets={"neighbors": _neighbors(), "call_volume": _volume()},
    )
    return voc_neighbor_correlation(ctx)


def test_gated_out_when_no_anchor():
    res = _run(anchor_found=False)
    assert res.summary["found"] is False
    assert res.table == []
    assert res.summary["volume_ts"]["series"] == []


def test_table_lists_anchor_first_then_neighbors():
    res = _run()
    rows = res.table
    assert [r["USID"] for r in rows] == ["A1", "A2"]  # anchor (distance 0) first
    assert rows[0]["Trend ID"] == "T1"
    assert rows[0]["Distance (km)"] == 0.0
    assert set(rows[0]) == {"Trend ID", "USID", "Trend start", "Duration", "Distance (km)", "Location type"}
    # the other anchor's trend must not leak in
    assert all(r["USID"] != "Z9" for r in rows)


def test_three_granularities_and_window_math():
    ts = _run().summary["volume_ts"]
    assert [g["key"] for g in ts["granularities"]] == ["daily", "3h", "hourly"]
    # daily window starts 30 days before the first trend start (floored to the day)
    daily_start = pd.to_datetime(ts["windows"]["daily"]["start"])
    assert daily_start == pd.Timestamp("2026-06-05T00:00:00Z") - pd.Timedelta(days=30)


def test_unparseable_starts_degrade_gracefully():
    bad = pd.DataFrame(
        [
            {"anchor_usid": "A1", "trend_id": "T1", "usid": "A1", "trend_start_time": "not-a-date",
             "trend_end_time": "", "trend_status": "Active", "distance_km": 0.0, "location_type": "urban"},
        ]
    )
    prior = AnalysisResult(summary={"found": True, "anchor": {"found": True, "usid": "A1"}})
    ctx = AnalysisContext(dataset=bad, params={}, inputs={}, results={"collect_trend": prior},
                          datasets={"call_volume": _volume()})
    res = voc_neighbor_correlation(ctx)
    assert res.summary["found"] is True
    assert res.summary["volume_ts"]["series"] == []  # no windows -> no series
    assert "no usable" in res.summary["volume_ts"]["notice"].lower()
    assert len(res.table) == 1  # table still rendered


def test_cluster_active_flag():
    # the sample neighbor trends are Active -> cluster_active true
    assert _run().summary["cluster_active"] is True


def test_cluster_active_from_anchor_when_no_neighbor_rows():
    # neighbors pull has NO rows for this anchor, but the anchor's own trend is Active
    prior = AnalysisResult(
        summary={"found": True, "anchor": {"found": True, "usid": "ZZ", "trend_status": "Active"}}
    )
    ctx = AnalysisContext(
        dataset=_neighbors(), params={}, inputs={},
        results={"collect_trend": prior}, datasets={"call_volume": _volume()},
    )
    assert voc_neighbor_correlation(ctx).summary["cluster_active"] is True


def test_window_end_never_in_future():
    from datetime import datetime, timezone
    before = pd.Timestamp(datetime.now(timezone.utc))
    ts = _run().summary["volume_ts"]
    after = pd.Timestamp(datetime.now(timezone.utc))
    for g in ("daily", "3h", "hourly"):
        end = pd.to_datetime(ts["windows"][g]["end"])
        assert before <= end <= after  # window ends at "now", not in the future


def test_trend_span_is_earliest_start_to_latest_end():
    ts = _run().summary["volume_ts"]
    span = ts["trend_span"]
    # earliest correlated start is 2026-06-05; both trends are ongoing -> end at now
    assert pd.to_datetime(span["start"]) == pd.Timestamp("2026-06-05T00:00:00Z")
    assert pd.to_datetime(span["end"]) >= pd.to_datetime(span["start"])


def test_series_roles_and_aggregate():
    ts = _run().summary["volume_ts"]
    by_role = {}
    for s in ts["series"]:
        by_role.setdefault(s["role"], []).append(s)
    assert [s["usid"] for s in by_role["anchor"]] == ["A1"]
    assert {s["usid"] for s in by_role["neighbor"]} == {"A2"}
    assert by_role["aggregate"][0]["usid"] == "__aggregate__"
    # every series carries aligned x/y for all granularities
    for s in ts["series"]:
        for g in ("daily", "3h", "hourly"):
            pts = s["by_gran"][g]
            assert len(pts["x"]) == len(pts["y"]) > 0


def test_aggregate_is_deduped_below_naive_sum():
    ts = _run().summary["volume_ts"]
    series = {s["role"]: s for s in ts["series"]}
    # pick a daily bin inside the data window where both USIDs have volume
    anchor_y = series["anchor"]["by_gran"]["daily"]["y"]
    # find an index with non-zero anchor volume
    i = next(k for k, v in enumerate(anchor_y) if v > 0)
    naive = sum(s["by_gran"]["daily"]["y"][i] for s in ts["series"] if s["role"] != "aggregate")
    agg = series["aggregate"]["by_gran"]["daily"]["y"][i]
    assert 0 < agg < naive  # dedup removes overlap
