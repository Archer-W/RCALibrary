from datetime import datetime, timedelta, timezone

import pandas as pd

from rcalibrary.analyzers.context import AnalysisContext
from usecases.netcare_voc import voc_collect_trend


def _df(last_update, status="Active", start="2026-06-10T00:00:00Z"):
    return pd.DataFrame(
        [
            {
                "trend_id": "T-1",
                "usid": "0123456",
                "trend_start_time": start,
                "trend_status": status,
                "last_update_time": last_update,
            }
        ]
    )


def _run(df, inputs):
    return voc_collect_trend(AnalysisContext(dataset=df, params={}, inputs=inputs)).summary


def _box(summary, label):
    for item in summary["trend_fields"]["items"]:
        if item["label"] == label:
            return item
    return None


def test_found_by_trend_id_and_fresh_is_green():
    now = datetime.now(timezone.utc)
    s = _run(_df((now - timedelta(hours=2)).isoformat()), {"_input_group": "trend_id", "trend_id": "T-1"})
    assert s["found"] is True
    assert _box(s, "Trend ID")["value"] == "T-1"
    assert _box(s, "USID")["value"] == "0123456"  # leading zero preserved
    assert s["delay_state"] == "good"  # < 6h


def test_status_colors_active_cooling_closed():
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(hours=1)).isoformat()
    inputs = {"_input_group": "trend_id", "trend_id": "T-1"}
    assert _box(_run(_df(fresh, status="Active"), inputs), "Trend status")["state"] == "bad"
    assert _box(_run(_df(fresh, status="Cooling"), inputs), "Trend status")["state"] == "warn"
    assert _box(_run(_df(fresh, status="Closed"), inputs), "Trend status")["state"] == "neutral"
    # case-insensitive + unknown status falls back to neutral
    assert _box(_run(_df(fresh, status="active"), inputs), "Trend status")["state"] == "bad"
    assert _box(_run(_df(fresh, status="weird"), inputs), "Trend status")["state"] == "neutral"


def test_duration_box_is_in_days():
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=5)).isoformat()
    s = _run(
        _df((now - timedelta(hours=1)).isoformat(), status="Active", start=start),
        {"_input_group": "trend_id", "trend_id": "T-1"},
    )
    assert "day" in _box(s, "Duration")["value"].lower()
    assert _box(s, "Duration")["value"].startswith("5")  # ~5 days since start


def test_stale_table_is_red():
    now = datetime.now(timezone.utc)
    s = _run(_df((now - timedelta(hours=10)).isoformat()), {"_input_group": "trend_id", "trend_id": "T-1"})
    assert s["delay_state"] == "bad"  # > 6h


def test_trend_id_not_found_message():
    s = _run(_df("2026-06-17T00:00:00Z"), {"_input_group": "trend_id", "trend_id": "NOPE"})
    assert s["found"] is False
    assert s["trend_fields"]["items"] == []
    assert "not found" in s["trend_fields"]["notice"].lower()


def test_usid_date_within_and_outside_window():
    now = datetime.now(timezone.utc)
    df = _df((now - timedelta(hours=1)).isoformat())
    inside = _run(df, {"_input_group": "usid_date", "usid": "0123456", "date": "2026-06-11"})
    assert inside["found"] is True  # within +/-7 days of 2026-06-10
    outside = _run(df, {"_input_group": "usid_date", "usid": "0123456", "date": "2026-08-01"})
    assert outside["found"] is False
    assert "no voc trend" in outside["trend_fields"]["notice"].lower()
