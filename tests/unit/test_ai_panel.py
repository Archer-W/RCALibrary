"""Unit tests for AI panel mode: the synthesis skill, the deterministic engine's
parsing/routing, the param-aware timeseries window, run_panel param overlay,
requires_ai validation, the tool surface, and the (optional) MCP tool server.

All offline/deterministic — no LLM, no network."""

from datetime import datetime, timezone

import pandas as pd
import pytest
from pydantic import ValidationError

from rcalibrary.ai import tools
from rcalibrary.ai.engine import SimulatedAIEngine, _extract_params, _norm_gran
from rcalibrary.ai.skills import default_registry as skills
from rcalibrary.deps import get_engine, get_template_registry
from rcalibrary.workflow.models import Template
from usecases.netcare_voc import _build_grids

T = "ana.rca.netcare-voc-trend"
G = ({"trend_id": "T-1001"}, "trend_id")  # (inputs, input_group)


# --- summarize_symptoms skill ------------------------------------------------
def test_skill_filters_non_network_and_counts_users():
    out = skills.get("summarize_symptoms")([
        {"usid": "1", "text": "my calls keep dropping downtown"},
        {"usid": "2", "text": "no signal at all, dead zone"},
        {"usid": "1", "text": "internet is so slow, buffering"},
        {"usid": "3", "text": "I want a refund on my bill"},        # non-network -> filtered
        {"usid": "2", "text": "calls drop mid-conversation"},
    ], filter_non_network=True)
    by = {b["symptom_type"]: b for b in out["breakdown"]}
    assert by["Dropped calls"]["n_users"] == 2          # users 1 and 2
    assert "No signal / coverage" in by and "Slow data / internet" in by
    assert out["filtered_out"] == 1
    assert out["n_users"] == 2                           # distinct NETWORK users (user 3 is billing-only)
    # ranked by user count desc
    assert out["breakdown"][0]["n_users"] >= out["breakdown"][-1]["n_users"]


def test_skill_handles_no_network_symptoms():
    out = skills.get("summarize_symptoms")([{"usid": "1", "text": "billing question only"}])
    assert out["breakdown"] == [] and out["filtered_out"] == 1


# --- NL parsing (deterministic stand-in for the LLM) -------------------------
def test_norm_gran_explicit_only():
    # The engine scans free text, so it is STRICT: bare "day"/"hour" are NOT a
    # granularity (avoids matching "day" inside "day X to day Y"); only "daily"/
    # "hourly"/"3-hourly" count.
    assert _norm_gran("hourly") == "hourly"
    assert _norm_gran("3-hourly") == "3h"
    assert _norm_gran("daily") == "daily"
    assert _norm_gran("day") is None
    assert _norm_gran("show me stuff") is None


def test_extract_params_dates_and_granularity():
    p = _extract_params("call volume from 2026-05-01 to 2026-05-20 at hourly granularity")
    assert p == {"granularity": "hourly", "date_start": "2026-05-01", "date_end": "2026-05-20"}


def test_extract_params_day_x_to_day_y_does_not_false_match_daily():
    # "day X to day Y at hourly" -> the bare word "day" must NOT override hourly.
    p = _extract_params("show call volume from day X to day Y at hourly granularity")
    assert p.get("granularity") == "hourly"


# --- param-aware window ------------------------------------------------------
def _ts(s):
    return pd.Timestamp(s, tz="UTC")


def test_build_grids_default_window_no_params():
    first, now = _ts("2026-06-10"), _ts("2026-06-26")
    grids, windows = _build_grids(first, now, None)
    assert set(windows) == {"daily", "3h", "hourly"}
    # daily opens 30 days before the first trend start by default
    assert windows["daily"]["start"].startswith("2026-05-11")
    assert windows["daily"]["end"].startswith("2026-06-26")


def test_build_grids_clamps_to_ai_dates():
    first, now = _ts("2026-06-10"), _ts("2026-06-26")
    _, windows = _build_grids(first, now, {"date_start": "2026-06-01", "date_end": "2026-06-05"})
    assert windows["hourly"]["start"].startswith("2026-06-01")
    assert windows["hourly"]["end"].startswith("2026-06-05")


def test_build_grids_inverted_range_falls_back():
    first, now = _ts("2026-06-10"), _ts("2026-06-26")
    _, windows = _build_grids(first, now, {"date_start": "2026-06-20", "date_end": "2026-06-01"})
    # start > end -> default window (end back at now)
    assert windows["daily"]["end"].startswith("2026-06-26")


# --- run_panel param overlay (engine.run_panel(..., params)) -----------------
def test_run_panel_applies_ai_params():
    reg = get_template_registry()
    eng = get_engine()
    template = reg.get(T)
    bundle = template.library_panel_by_id("call_volume_trend")
    panel, _ = eng.run_panel(
        template, bundle, {"trend_id": "T-1001"}, None, input_group="trend_id",
        params={"granularity": "hourly", "date_start": "2026-06-01", "date_end": "2026-06-05"},
    )
    assert panel.type == "timeseries"
    assert panel.timeseries.default_granularity == "hourly"   # AI granularity honored
    assert panel.timeseries.windows["hourly"]["start"].startswith("2026-06-01")
    # default (no params) keeps daily
    panel2, _ = eng.run_panel(template, bundle, {"trend_id": "T-1001"}, None, input_group="trend_id")
    assert panel2.timeseries.default_granularity == "daily"


# --- requires_ai validation --------------------------------------------------
def test_library_panel_requires_ai_flag_loads():
    t = Template.model_validate({
        "meta": {"id": "t", "name": "t"},
        "data_pulls": [{"id": "d", "query": {"dataset": "d"}}],
        "report": {"panels": []},
        "panel_library": [{
            "id": "ai_only", "title": "x", "requires_ai": True,
            "panel": {"id": "p", "type": "markdown", "title": "x"},
        }],
    })
    assert t.library_panel_by_id("ai_only").requires_ai is True


# --- tool surface ------------------------------------------------------------
def test_tools_list_library_panels_marks_params_and_ai():
    template = get_template_registry().get(T)
    lib = {p["id"]: p for p in tools.list_library_panels(template)}
    assert lib["call_volume_trend"]["params"] == ["date_start", "date_end", "granularity"]
    assert lib["complaint_pie"]["params"] == []          # pie is not parameterized
    assert lib["transcript_summary"]["requires_ai"] is True


def test_tools_build_panel_and_run_skill():
    template = get_template_registry().get(T)
    panel, _ = tools.build_panel(get_engine(), template, "complaint_pie",
                                 {"trend_id": "T-1001"}, "trend_id", {}, None)
    assert panel.type == "pie"
    out = tools.run_skill("summarize_symptoms", transcripts=[{"usid": "1", "text": "calls dropping"}])
    assert out["breakdown"][0]["symptom_type"] == "Dropped calls"


# --- the simulated engine directly -------------------------------------------
def _engine():
    return SimulatedAIEngine(get_engine())


def test_engine_clarifies_then_builds_call_volume():
    eng, template = _engine(), get_template_registry().get(T)
    r1 = eng.chat(None, "show me the call volume chart", template=template,
                  inputs={"trend_id": "T-1001"}, input_group="trend_id", principal=None)
    assert r1["status"] == "needs_input" and r1["session_id"]
    r2 = eng.chat(r1["session_id"], "hourly from 2026-06-01 to 2026-06-05", template=template,
                  inputs={"trend_id": "T-1001"}, input_group="trend_id", principal=None)
    assert r2["status"] == "panel"
    assert r2["panel"].timeseries.default_granularity == "hourly"


def test_engine_builds_transcript_panel():
    eng, template = _engine(), get_template_registry().get(T)
    r = eng.chat(None, "summarize the symptom types from the call transcripts", template=template,
                 inputs={"trend_id": "T-1001"}, input_group="trend_id", principal=None)
    assert r["status"] == "panel" and r["panel"].type == "markdown"
    assert "Symptom breakdown" in (r["panel"].markdown or "")


def test_engine_cannot_satisfy_unknown_request():
    eng, template = _engine(), get_template_registry().get(T)
    r = eng.chat(None, "export the whole report to a PDF and email it", template=template,
                 inputs={"trend_id": "T-1001"}, input_group="trend_id", principal=None)
    assert r["status"] == "cannot_satisfy" and r["panel"] is None


# --- optional MCP tool server (skips if `mcp` not installed) ------------------
def test_mcp_server_exposes_tools():
    pytest.importorskip("mcp")
    from rcalibrary.ai.mcp_server import build_mcp_server

    server = build_mcp_server(get_template_registry(), get_engine(), None)
    # FastMCP exposes registered tools; names must include the four surface tools.
    import anyio

    names = {t.name for t in anyio.run(server.list_tools)}
    assert {"list_library_panels", "describe_template", "build_panel", "run_skill"} <= names
