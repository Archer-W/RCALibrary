from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from rcalibrary.analyzers import default_registry
from rcalibrary.analyzers.context import AnalysisContext, AnalysisResult
from rcalibrary.errors import TemplateValidationError
from rcalibrary.persistence.report_cache import ReportCache, ReportCacheError, _safe_dir
from rcalibrary.reporting.contract import PanelPayload
from rcalibrary.workflow import report_builder
from rcalibrary.workflow.loader import TemplateLoader
from rcalibrary.workflow.models import PanelEncoding, PanelSpec, Template
from usecases.netcare_voc import voc_complaint_distribution, voc_rrc_kpi

# --- template panel_library validation --------------------------------------
_BASE = {
    "meta": {"id": "t", "name": "t"},
    "data_pulls": [{"id": "d", "query": {"dataset": "d"}}],
    "report": {"panels": [{"id": "p1", "type": "stat", "title": "P"}]},
}


def test_library_valid_with_own_pull_and_analysis():
    ok = {**_BASE, "panel_library": [{
        "id": "lib", "title": "x",
        "data_pulls": [{"id": "lp_pull", "query": {"dataset": "lp_pull"}}],
        "analysis": [{"id": "lp_an", "analyzer": "passthrough", "inputs": {"dataset": "lp_pull"}}],
        "panel": {"id": "lp", "type": "pie", "title": "x", "analysis_ref": "lp_an", "dataset": "lp_pull"},
    }]}
    t = Template.model_validate(ok)
    assert t.library_panel_by_id("lib") is not None and t.library_panel_by_id("nope") is None


def test_library_id_clashing_with_report_panel_rejected():
    bad = {**_BASE, "panel_library": [
        {"id": "p1", "title": "x", "panel": {"id": "lp", "type": "pie", "title": "x"}}
    ]}
    with pytest.raises(ValidationError):
        Template.model_validate(bad)


def test_library_panel_bad_analysis_ref_rejected():
    bad = {**_BASE, "panel_library": [
        {"id": "lib", "title": "x", "panel": {"id": "lp", "type": "pie", "title": "x", "analysis_ref": "nope"}}
    ]}
    with pytest.raises(ValidationError):
        Template.model_validate(bad)


def test_library_pull_id_collision_with_main_rejected():
    bad = {
        "meta": {"id": "t", "name": "t"},
        "data_pulls": [{"id": "shared", "query": {"dataset": "shared"}}],
        "report": {"panels": []},
        "panel_library": [{
            "id": "lib", "title": "x",
            "data_pulls": [{"id": "shared", "query": {"dataset": "shared"}}],  # collides with main
            "panel": {"id": "lp", "type": "pie", "title": "x", "dataset": "shared"},
        }],
    }
    with pytest.raises(ValidationError):
        Template.model_validate(bad)


def test_library_analysis_id_collision_with_main_rejected():
    bad = {
        "meta": {"id": "t", "name": "t"},
        "data_pulls": [{"id": "d", "query": {"dataset": "d"}}],
        "analysis": [{"id": "shared_an", "analyzer": "passthrough", "inputs": {"dataset": "d"}}],
        "report": {"panels": []},
        "panel_library": [{
            "id": "lib", "title": "x",
            "analysis": [{"id": "shared_an", "analyzer": "passthrough", "inputs": {"dataset": "d"}}],
            "panel": {"id": "lp", "type": "stat", "title": "x", "analysis_ref": "shared_an"},
        }],
    }
    with pytest.raises(ValidationError):
        Template.model_validate(bad)


def test_loader_rejects_unknown_library_analyzer():
    # a library bundle referencing an unregistered analyzer must be caught at LOAD,
    # so the template is skipped at discovery (resilience) instead of 500-ing on add.
    t = Template.model_validate({**_BASE,
        "analysis": [{"id": "m", "analyzer": "passthrough", "inputs": {"dataset": "d"}}],
        "panel_library": [{
            "id": "lib", "title": "x",
            "analysis": [{"id": "la", "analyzer": "definitely_not_registered", "inputs": {"dataset": "d"}}],
            "panel": {"id": "lp", "type": "pie", "title": "x", "analysis_ref": "la"},
        }]})
    with pytest.raises(TemplateValidationError):
        TemplateLoader(default_registry)._check_analyzers(t, Path("x.yaml"))


def test_library_analysis_can_chain_on_main_step():
    # a library analysis step may reference a MAIN data pull (union of pulls)
    ok = {
        "meta": {"id": "t", "name": "t"},
        "data_pulls": [{"id": "main", "query": {"dataset": "main"}}],
        "analysis": [{"id": "main_an", "analyzer": "passthrough", "inputs": {"dataset": "main"}}],
        "report": {"panels": []},
        "panel_library": [{
            "id": "lib", "title": "x",
            "analysis": [{"id": "lib_an", "analyzer": "passthrough", "inputs": {"dataset": "main"}}],
            "panel": {"id": "lp", "type": "stat", "title": "x", "analysis_ref": "lib_an"},
        }],
    }
    assert Template.model_validate(ok).library_panel_by_id("lib") is not None


# --- report cache ------------------------------------------------------------
def test_report_cache_put_get_and_key_stability(tmp_path):
    cache = ReportCache(tmp_path)
    inputs = {"trend_id": "T-1001"}
    assert cache.exists("tpl", "g", inputs) is False
    cache.put("tpl", "g", inputs, {"title": "saved", "panels": []})
    assert cache.exists("tpl", "g", inputs) is True
    assert cache.get("tpl", "g", inputs)["title"] == "saved"
    # different inputs -> different key (miss); key is order-independent
    assert cache.get("tpl", "g", {"trend_id": "other"}) is None
    assert ReportCache.key("tpl", "g", {"a": 1, "b": 2}) == ReportCache.key("tpl", "g", {"b": 2, "a": 1})


def test_report_cache_bad_json_returns_none(tmp_path):
    cache = ReportCache(tmp_path)
    p = tmp_path / "tpl" / f"{ReportCache.key('tpl', None, {})}.json"
    p.parent.mkdir(parents=True)
    p.write_text("{not json")
    assert cache.get("tpl", None, {}) is None


def test_report_cache_scope_isolates_keys():
    base = ReportCache.key("t", "g", {"x": 1})
    assert ReportCache.key("t", "g", {"x": 1}, "v1|alice") != base                       # scope changes key
    assert ReportCache.key("t", "g", {"x": 1}, "v1|alice") != ReportCache.key("t", "g", {"x": 1}, "v2|alice")  # version
    assert ReportCache.key("t", "g", {"x": 1}, "v1|alice") != ReportCache.key("t", "g", {"x": 1}, "v1|bob")    # principal


def test_report_cache_size_cap(tmp_path):
    cache = ReportCache(tmp_path, max_bytes=50)
    with pytest.raises(ReportCacheError):
        cache.put("t", None, {}, {"big": "x" * 1000})


def test_safe_dir_neutralizes_path_traversal():
    # a bare dot-component is the traversal risk -> neutralized to "_"
    assert _safe_dir("..") == "_" and _safe_dir(".") == "_" and _safe_dir("") == "_"
    # slashes are collapsed so the result is always a single, non-traversing component
    r = _safe_dir("a/b/../c")
    assert "/" not in r and r != ".."


def test_fill_pie_degrades_to_markdown_when_empty():
    spec = PanelSpec(id="p", type="pie", title="P", encoding=PanelEncoding(labels="t", values="c"))
    ar = AnalysisResult(summary={"empty_notice": "No complaints for this cluster."}, table=[])
    panel = PanelPayload(id="p", type="pie", title="P", width="half")
    report_builder._fill_pie(spec, {}, ar, panel)
    assert panel.type == "markdown" and "No complaints" in panel.markdown


# --- pie report builder ------------------------------------------------------
def test_fill_pie_builds_pie_trace():
    spec = PanelSpec(id="p", type="pie", title="P",
                     encoding=PanelEncoding(labels="complaint_type", values="count"))
    ar = AnalysisResult(table=[{"complaint_type": "Voice", "count": 10}, {"complaint_type": "Data", "count": 5}])
    panel = PanelPayload(id="p", type="pie", title="P", width="half")
    report_builder._fill_pie(spec, {}, ar, panel)
    tr = panel.traces[0]
    assert tr["type"] == "pie" and tr["labels"] == ["Voice", "Data"] and tr["values"] == [10, 5]


# --- library analyzers (direct ctx, like test_voc_map_build) -----------------
def _trend_results(extra=None):
    res = {
        "collect_trend": AnalysisResult(summary={"found": True, "anchor": {"found": True, "usid": "A1"}}),
        "neighbor_correlation": AnalysisResult(summary={
            "cluster_usids": ["A1", "A2"],
            "trend_span": {"start": "2026-06-10T00:00:00Z", "end": "2026-06-15T00:00:00Z"},
        }),
    }
    if extra:
        res.update(extra)
    return res


def test_complaint_distribution_sums_cluster_only():
    df = pd.DataFrame([
        {"usid": "A1", "complaint_type": "Voice", "count": 10},
        {"usid": "A1", "complaint_type": "Data", "count": 5},
        {"usid": "A2", "complaint_type": "Voice", "count": 3},
        {"usid": "FAR", "complaint_type": "Voice", "count": 99},  # outside cluster -> excluded
    ])
    ctx = AnalysisContext(dataset=df, params={}, inputs={}, results=_trend_results(), datasets={})
    out = voc_complaint_distribution(ctx)
    by_type = {r["complaint_type"]: r["count"] for r in out.table}
    assert by_type["Voice"] == 13 and by_type["Data"] == 5  # FAR excluded
    assert out.summary["total_complaints"] == 18
    assert out.table[0]["complaint_type"] == "Voice"  # sorted desc


def test_rrc_kpi_series_includes_cluster_and_ticket_usids():
    grid = pd.date_range("2026-06-01", "2026-06-20", freq="h", tz="UTC")
    rows = [{"usid": u, "timestamp": t.isoformat(), "rrc_conn": 100} for u in ("A1", "A2", "TK") for t in grid]
    df = pd.DataFrame(rows)
    res = _trend_results({"ticket_search": AnalysisResult(summary={
        "ticket_overlay": [{"usid": "TK", "id": "T1", "type": "Outage"}]})})
    ctx = AnalysisContext(dataset=df, params={}, inputs={}, results=res, datasets={})
    ts = voc_rrc_kpi(ctx).summary["rrc_ts"]
    usids = [s["usid"] for s in ts["series"]]
    assert usids[0] == "A1" and ts["series"][0]["role"] == "anchor"  # searched first
    assert "A2" in usids and "TK" in usids  # cluster + ticket USID
    assert set(ts["windows"]) == {"daily", "3h", "hourly"}
    daily = ts["series"][0]["by_gran"]["daily"]
    assert len(daily["x"]) == len(daily["y"]) > 0


def test_rrc_kpi_gated_when_not_found():
    res = {"collect_trend": AnalysisResult(summary={"found": False, "anchor": {"found": False}})}
    ctx = AnalysisContext(dataset=pd.DataFrame(), params={}, inputs={}, results=res, datasets={})
    out = voc_rrc_kpi(ctx).summary
    assert out["found"] is False and out["rrc_ts"]["series"] == []
