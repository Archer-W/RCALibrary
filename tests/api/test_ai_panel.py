"""API tests for the AI 'build a panel' chat endpoint (multi-turn). Uses the
shipped simulated engine (free/offline) — no LLM. Disabled mode is exercised by
overriding the engine dependency."""

import pytest
from fastapi.testclient import TestClient

from rcalibrary.ai.engine import DisabledAIEngine
from rcalibrary.deps import get_ai_panel_engine
from rcalibrary.main import app

T = "ana.rca.netcare-voc-trend"
G = {"inputs": {"trend_id": "T-1001"}, "input_group": "trend_id"}


def _chat(client, message, session_id=None):
    body = {"message": message, **G}
    if session_id:
        body["session_id"] = session_id
    return client.post(f"/api/templates/{T}/panel/ai", json=body)


def test_chat_multiturn_clarify_then_build(client):
    r1 = _chat(client, "show me the call volume chart").json()
    assert r1["status"] == "needs_input" and r1["session_id"] and r1["panel"] is None
    r2 = _chat(client, "hourly from 2026-06-01 to 2026-06-05", r1["session_id"]).json()
    assert r2["status"] == "panel"
    assert r2["panel"]["type"] == "timeseries"
    assert r2["panel"]["timeseries"]["default_granularity"] == "hourly"


def test_chat_one_shot_with_params(client):
    r = _chat(client, "call volume daily").json()
    assert r["status"] == "panel"
    assert r["panel"]["timeseries"]["default_granularity"] == "daily"


def test_chat_builds_transcript_panel(client):
    r = _chat(client, "summarize the symptom types from the call transcripts").json()
    assert r["status"] == "panel" and r["panel"]["type"] == "markdown"
    assert "Symptom breakdown" in (r["panel"]["markdown"] or "")


def test_chat_cannot_satisfy(client):
    r = _chat(client, "export everything to a PDF and email it").json()
    assert r["status"] == "cannot_satisfy" and r["panel"] is None
    assert "available templates" in r["reply"].lower()


def test_chat_disabled_engine_returns_disabled():
    app.dependency_overrides[get_ai_panel_engine] = lambda: DisabledAIEngine()
    try:
        c = TestClient(app)
        r = _chat(c, "anything").json()
        assert r["status"] == "disabled" and r["panel"] is None
    finally:
        app.dependency_overrides.pop(get_ai_panel_engine, None)


def test_chat_unknown_template_404(client):
    assert client.post("/api/templates/nope/panel/ai", json={"message": "x"}).status_code == 404
