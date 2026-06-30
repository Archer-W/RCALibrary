"""Offline tests for the real-LLM routing engine (`LLMToolEngine`) and the
OpenAI-compatible client's response parsing. No network / no LLM: the engine is driven
by a scripted `FakeLLMClient`, and the gpt-oss adapter is tested by injecting a fake
`openai`-shaped client. Everything runs free/offline."""

from types import SimpleNamespace

from rcalibrary.ai.engine import LLMToolEngine
from rcalibrary.ai.llm import FakeLLMClient, LLMReply, OpenAICompatLLMClient
from rcalibrary.deps import get_engine, get_template_registry

T = "ana.rca.netcare-voc-trend"
INP, IG = {"trend_id": "T-1001"}, "trend_id"


def _engine(script, **kw):
    return LLMToolEngine(get_engine(), FakeLLMClient(script), **kw)


def _template():
    return get_template_registry().get(T)


def _chat(eng, msg, sid=None):
    return eng.chat(sid, msg, template=_template(), inputs=INP, input_group=IG, principal=None)


# --- tool schemas mirror the contract ---------------------------------------
def test_prompt_and_tools_enumerates_library_ids_and_three_actions():
    eng = _engine([])
    system, tools = eng._prompt_and_tools(_template())
    by = {t["name"]: t for t in tools}
    assert set(by) == {"build_panel", "ask_clarification", "cannot_satisfy"}
    lib_ids = {b.id for b in _template().panel_library}
    assert set(by["build_panel"]["parameters"]["properties"]["panel_id"]["enum"]) == lib_ids
    assert "call_volume_trend" in system  # catalog injected into the prompt


# --- the tool-calling loop ---------------------------------------------------
def test_clarify_then_build_multiturn():
    eng = _engine([
        {"name": "ask_clarification", "arguments": {"question": "Which granularity?"}},
        {"name": "build_panel", "arguments": {
            "panel_id": "call_volume_trend", "granularity": "hourly",
            "date_start": "2026-06-01", "date_end": "2026-06-05"}},
    ])
    r1 = _chat(eng, "show call volume")
    assert r1["status"] == "needs_input" and r1["panel"] is None and r1["session_id"]
    r2 = _chat(eng, "hourly, 2026-06-01 to 2026-06-05", r1["session_id"])
    assert r2["status"] == "panel"
    ts = r2["panel"].timeseries
    assert ts.default_granularity == "hourly"
    assert ts.windows["hourly"]["start"].startswith("2026-06-01")


def test_one_shot_build():
    eng = _engine([{"name": "build_panel", "arguments": {"panel_id": "call_volume_trend", "granularity": "daily"}}])
    r = _chat(eng, "call volume daily")
    assert r["status"] == "panel" and r["panel"].timeseries.default_granularity == "daily"


def test_cannot_satisfy_tool():
    eng = _engine([{"name": "cannot_satisfy", "arguments": {"reason": "No panel for PDF export."}}])
    r = _chat(eng, "export to pdf")
    assert r["status"] == "cannot_satisfy" and "PDF" in r["reply"]


def test_invalid_panel_id_retries_then_builds():
    eng = _engine([
        {"name": "build_panel", "arguments": {"panel_id": "does_not_exist"}},   # corrected...
        {"name": "build_panel", "arguments": {"panel_id": "complaint_pie"}},     # ...on retry
    ])
    r = _chat(eng, "complaint distribution")
    assert r["status"] == "panel" and r["panel"].type == "pie"


def test_invalid_panel_id_twice_declines():
    eng = _engine([
        {"name": "build_panel", "arguments": {"panel_id": "nope1"}},
        {"name": "build_panel", "arguments": {"panel_id": "nope2"}},
    ])
    r = _chat(eng, "something")
    assert r["status"] == "cannot_satisfy"


def test_text_reply_becomes_clarification():
    eng = _engine([LLMReply(text="Which date range would you like?")])
    r = _chat(eng, "call volume")
    assert r["status"] == "needs_input" and "date range" in r["reply"]


def test_endpoint_error_degrades_gracefully():
    eng = _engine([RuntimeError("connection refused")])
    r = _chat(eng, "call volume")
    assert r["status"] == "cannot_satisfy" and "unavailable" in r["reply"].lower()


def test_routes_to_requires_ai_transcript_panel():
    eng = _engine([{"name": "build_panel", "arguments": {"panel_id": "transcript_summary"}}])
    r = _chat(eng, "summarize symptom types from transcripts")
    assert r["status"] == "panel" and r["panel"].type == "markdown"
    assert "Symptom breakdown" in (r["panel"].markdown or "")


def test_max_turns_cap():
    eng = _engine([{"name": "ask_clarification", "arguments": {"question": "?"}}], max_turns=1)
    r1 = _chat(eng, "call volume")
    assert r1["status"] == "needs_input"
    r2 = _chat(eng, "again", r1["session_id"])  # turn 2 > max_turns=1
    assert r2["status"] == "cannot_satisfy" and "fresh" in r2["reply"].lower()


# --- OpenAI-compatible adapter parsing (no network; fake openai client) ------
def _fake_openai_client(response):
    return SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=lambda **kw: response)))


def _resp(*, name=None, arguments=None, content=None):
    tool_calls = []
    if name is not None:
        tool_calls = [SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))]
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_openai_adapter_parses_tool_call():
    client = OpenAICompatLLMClient(base_url="http://x/v1", model="gpt-oss")
    client._client = _fake_openai_client(_resp(name="build_panel", arguments='{"panel_id":"p","granularity":"daily"}'))
    reply = client.respond("sys", [{"role": "user", "content": "hi"}], [{"name": "build_panel"}])
    assert reply.tool_call == {"name": "build_panel", "arguments": {"panel_id": "p", "granularity": "daily"}}


def test_openai_adapter_text_fallback_and_bad_json():
    client = OpenAICompatLLMClient(base_url="http://x/v1", model="gpt-oss")
    client._client = _fake_openai_client(_resp(content="please clarify"))
    assert client.respond("s", [{"role": "user", "content": "x"}], []).text == "please clarify"
    # malformed tool args -> empty dict (never raises)
    client._client = _fake_openai_client(_resp(name="build_panel", arguments="{not json"))
    assert client.respond("s", [{"role": "user", "content": "x"}], []).tool_call["arguments"] == {}
