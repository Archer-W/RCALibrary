import pandas as pd

from rcalibrary.analyzers.context import AnalysisContext, AnalysisResult
from usecases.netcare_voc import voc_map_build


def _sites():
    return pd.DataFrame(
        [
            {"usid": "A1", "lat": 10.0, "lon": 20.0},
            {"usid": "A2", "lat": 10.01, "lon": 20.0},   # ~1.1 km from A1
            {"usid": "N1", "lat": 10.02, "lon": 20.0},   # ~2.2 km — no-trend neighbor
            {"usid": "FAR", "lat": 11.0, "lon": 20.0},   # ~111 km — excluded
        ]
    )


def _results():
    return {
        "collect_trend": AnalysisResult(summary={"found": True, "anchor": {"found": True, "usid": "A1"}}),
        "neighbor_correlation": AnalysisResult(summary={
            "cluster_usids": ["A1", "A2"],
            "cluster_meta": {
                "A1": {"status": "Active", "start": "2026-06-05T00:00:00Z", "close": None},
                "A2": {"status": "Closed", "start": "2026-06-04T00:00:00Z", "close": "2026-06-10T00:00:00Z"},
            },
            "usid_window_calls": {"A1": 100, "A2": 50},
            "trend_span": {"start": "2026-06-05T00:00:00Z", "end": "2026-06-19T00:00:00Z"},
            "cluster_total_calls": 128,
        }),
        "ticket_search": AnalysisResult(summary={"ticket_overlay": [
            {"id": "TK1", "usid": "A2", "type": "Outage", "tone": "green",
             "start": "2026-06-10T00:00:00Z", "end": "2026-06-11T00:00:00Z", "prt": "2026-06-11T04:00:00Z"},
        ]}),
    }


def _run(sites=None, results=None):
    ctx = AnalysisContext(dataset=sites if sites is not None else _sites(), params={}, inputs={},
                          results=results if results is not None else _results(), datasets={})
    return voc_map_build(ctx).summary


def test_map_roles_colors_and_3km_neighbors():
    m = _run()["map_data"]
    feats = {f["usid"]: f for f in m["features"]}
    assert feats["A1"]["role"] == "cluster" and feats["A1"]["color"] == "#c0392b"  # Active -> red
    assert feats["A2"]["role"] == "cluster" and feats["A2"]["color"] == "#0568AE"  # Closed -> blue
    assert feats["A1"]["total_calls"] == 100
    assert feats["N1"]["role"] == "neighbor" and feats["N1"]["color"] == "#475569"  # within 3 km, slate (no-trend)
    assert "FAR" not in feats  # > 3 km from any trend/ticket site -> excluded
    assert len(feats["A2"]["tickets"]) == 1  # ticket tag attached to its USID
    assert m["cluster_total_calls"] == 128
    assert m["center"] and m["missing_coords"] == 0
    # trend start/close + ticket PRT carried for the detail panel
    assert feats["A1"]["trend_start"] == "2026-06-05T00:00:00Z" and feats["A1"]["trend_close"] is None
    assert feats["A2"]["trend_close"] == "2026-06-10T00:00:00Z"
    assert feats["A2"]["tickets"][0]["prt"] == "2026-06-11T04:00:00Z"


def test_map_no_trend_site_with_ticket_keeps_slate_and_carries_ticket():
    # a non-cluster, in-range site with a ticket -> role "ticket", still slate
    # (the red centre marker, not the site color, signals that it has tickets)
    res = _results()
    res["ticket_search"] = AnalysisResult(summary={"ticket_overlay": [
        {"id": "TK9", "usid": "N1", "type": "Outage", "tone": "green",
         "start": "2026-06-10T00:00:00Z", "end": "2026-06-11T00:00:00Z", "prt": None},
    ]})
    feats = {f["usid"]: f for f in _run(results=res)["map_data"]["features"]}
    assert feats["N1"]["role"] == "ticket"
    assert feats["N1"]["color"] == "#475569"          # no-trend stays slate
    assert len(feats["N1"]["tickets"]) == 1           # ticket attached -> red mark will render


def test_map_gated_when_not_found():
    s = _run(results={"collect_trend": AnalysisResult(summary={"found": False, "anchor": {"found": False}})})
    assert s["found"] is False
    assert s["map_data"]["features"] == []


def test_map_counts_missing_coordinates():
    sites = pd.DataFrame([{"usid": "A1", "lat": "", "lon": ""}])  # no inventory coords
    res = _results()
    res["neighbor_correlation"] = AnalysisResult(summary={
        "cluster_usids": ["A1"], "cluster_meta": {"A1": {"status": "Active"}},
        "usid_window_calls": {}, "trend_span": {}, "cluster_total_calls": 0,
    })
    res["ticket_search"] = AnalysisResult(summary={"ticket_overlay": []})
    m = _run(sites=sites, results=res)["map_data"]
    assert m["missing_coords"] == 1
    assert m["center"] is None  # nothing plottable
    assert "no sites have coordinates" in m["notice"].lower()


def test_map_partial_coordinate_is_off_map_not_a_crash():
    # one coordinate present, the other missing -> treated as off-map (no crash)
    sites = pd.DataFrame([{"usid": "A1", "lat": 10.0, "lon": ""}, {"usid": "A2", "lat": 10.01, "lon": 20.0}])
    res = _results()
    res["neighbor_correlation"] = AnalysisResult(summary={
        "cluster_usids": ["A1", "A2"], "cluster_meta": {"A1": {"status": "Active"}, "A2": {"status": "Closed"}},
        "usid_window_calls": {"A2": 5}, "trend_span": {}, "cluster_total_calls": 4,
    })
    res["ticket_search"] = AnalysisResult(summary={"ticket_overlay": []})
    m = _run(sites=sites, results=res)["map_data"]
    feats = {f["usid"]: f for f in m["features"]}
    assert feats["A1"]["lon"] is None and m["missing_coords"] == 1  # A1 off-map, counted
    assert m["center"] == {"lat": 10.01, "lon": 20.0}  # only A2 plottable


def test_map_calls_known_flag():
    m = _run()["map_data"]
    feats = {f["usid"]: f for f in m["features"]}
    assert feats["A1"]["calls_known"] is True   # A1 has call data
    assert feats["N1"]["calls_known"] is False  # neighbor with no call data
