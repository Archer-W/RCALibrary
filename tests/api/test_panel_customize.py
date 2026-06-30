"""API tests for the panel-customization feature: add a library panel on demand,
save a report, and reload it from cache on the same key."""

import pytest
from fastapi.testclient import TestClient

from rcalibrary.deps import get_report_cache
from rcalibrary.main import app
from rcalibrary.persistence.report_cache import ReportCache

T = "ana.rca.netcare-voc-trend"
G = {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"}


@pytest.fixture
def cclient(tmp_path):
    """A client with an isolated (tmp) report cache so save/reload tests don't
    touch the real cache dir or leak between tests."""
    app.dependency_overrides[get_report_cache] = lambda: ReportCache(tmp_path)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_report_cache, None)


def test_template_detail_exposes_library_and_ai_flag(cclient):
    d = cclient.get(f"/api/templates/{T}").json()
    ids = {p["id"] for p in d["panel_library"]}
    assert {"complaint_pie", "rrc_kpi"} <= ids
    assert d["ai_panels"] is True  # AI chat enabled for this template (see docs/11)
    # library panels are NOT part of the default report
    assert all(p["id"] not in ("complaint_pie", "rrc_kpi") for p in d["report_preview"])


def test_default_run_excludes_library_panels(cclient):
    r = cclient.post(f"/api/templates/{T}/run", json=G).json()
    pids = {p["id"] for p in r["report"]["panels"]}
    assert "complaint_pie" not in pids and "rrc_kpi" not in pids
    assert r["from_cache"] is False


def test_add_complaint_pie_panel(cclient):
    r = cclient.post(f"/api/templates/{T}/panel", json={**G, "panel_id": "complaint_pie"})
    assert r.status_code == 200
    panel = r.json()["panel"]
    assert panel["type"] == "pie"
    tr = panel["traces"][0]
    assert tr["type"] == "pie" and len(tr["labels"]) == len(tr["values"]) > 0


def test_add_rrc_kpi_panel_reuses_ticket_overlay(cclient):
    r = cclient.post(f"/api/templates/{T}/panel", json={**G, "panel_id": "rrc_kpi"})
    assert r.status_code == 200
    panel = r.json()["panel"]
    assert panel["type"] == "timeseries"
    ts = panel["timeseries"]
    assert len(ts["series"]) >= 1
    assert ts["series"][0]["role"] == "anchor"  # searched USID first
    assert len(ts["tickets"]) > 0  # ticket bands reused from Step 3 (overlay_ref)


def test_unknown_library_panel_is_404(cclient):
    assert cclient.post(f"/api/templates/{T}/panel", json={**G, "panel_id": "nope"}).status_code == 404


def test_manual_add_rejects_ai_only_panel(cclient):
    # requires_ai panels need NL input — they are AI-chat-only (see tests/api/test_ai_panel.py).
    r = cclient.post(f"/api/templates/{T}/panel", json={**G, "panel_id": "transcript_summary"})
    assert r.status_code == 400


def test_save_rejects_oversized_report(tmp_path):
    app.dependency_overrides[get_report_cache] = lambda: ReportCache(tmp_path, max_bytes=200)
    try:
        client = TestClient(app)
        big = {"title": "x", "panels": [], "blob": "z" * 5000}
        r = client.post(f"/api/templates/{T}/save", json={**G, "report": big})
        assert r.status_code == 413
    finally:
        app.dependency_overrides.pop(get_report_cache, None)


def test_save_then_reload_same_key_from_cache(cclient):
    run = cclient.post(f"/api/templates/{T}/run", json=G).json()
    saved = {**run["report"], "title": "Saved customized report"}
    sv = cclient.post(f"/api/templates/{T}/save", json={**G, "report": saved})
    assert sv.status_code == 200 and sv.json()["saved"] is True
    # same key -> loads the saved report (no recompute)
    r2 = cclient.post(f"/api/templates/{T}/run", json=G).json()
    assert r2["from_cache"] is True and r2["report"]["title"] == "Saved customized report"
    # refresh=True bypasses the cache and recomputes the default
    r3 = cclient.post(f"/api/templates/{T}/run", json={**G, "refresh": True}).json()
    assert r3["from_cache"] is False and r3["report"]["title"] != "Saved customized report"
