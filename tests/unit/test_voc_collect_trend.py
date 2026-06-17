from datetime import datetime, timedelta, timezone

import pandas as pd

from rcalibrary.analyzers.context import AnalysisContext
from usecases.netcare_voc import voc_collect_trend


def _df(last_update):
    return pd.DataFrame(
        [
            {
                "trend_id": "T-1",
                "usid": "0123456",
                "trend_start_time": "2026-06-10T00:00:00Z",
                "trend_status": "open",
                "last_update_time": last_update,
            }
        ]
    )


def _run(df, inputs):
    return voc_collect_trend(AnalysisContext(dataset=df, params={}, inputs=inputs)).summary


def test_found_by_trend_id_and_fresh_is_green():
    now = datetime.now(timezone.utc)
    s = _run(_df((now - timedelta(hours=2)).isoformat()), {"_input_group": "trend_id", "trend_id": "T-1"})
    assert s["found"] is True
    assert "T-1" in s["trend_md"]
    assert s["delay_state"] == "good"  # < 6h


def test_stale_table_is_red():
    now = datetime.now(timezone.utc)
    s = _run(_df((now - timedelta(hours=10)).isoformat()), {"_input_group": "trend_id", "trend_id": "T-1"})
    assert s["delay_state"] == "bad"  # > 6h


def test_trend_id_not_found_message():
    s = _run(_df("2026-06-17T00:00:00Z"), {"_input_group": "trend_id", "trend_id": "NOPE"})
    assert s["found"] is False
    assert "not found" in s["trend_md"].lower()


def test_usid_date_within_and_outside_window():
    now = datetime.now(timezone.utc)
    df = _df((now - timedelta(hours=1)).isoformat())
    inside = _run(df, {"_input_group": "usid_date", "usid": "0123456", "date": "2026-06-11"})
    assert inside["found"] is True  # within +/-7 days of 2026-06-10
    outside = _run(df, {"_input_group": "usid_date", "usid": "0123456", "date": "2026-08-01"})
    assert outside["found"] is False
    assert "no voc trend" in outside["trend_md"].lower()
