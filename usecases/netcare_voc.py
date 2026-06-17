"""NetCare VoC Trend Triage — Step 1: collect trend information.

Registered as a plugin analyzer (`voc_collect_trend`). Owns the workflow LOGIC;
the data SOURCE is the swap point for the data agent (dummy CSV via the sample
provider now -> real Snowflake later). See
templates/ana.rca.netcare-voc-trend/IMPLEMENTATION.md.

Step 1 branches on the chosen input set (``_input_group``):
  * ``trend_id``  -> look up the trend by its USID-level Trend ID
  * ``usid_date`` -> look up the trend by USID near the provided date
Output: Trend ID, USID, trend start time, status, last update time. If not
found, a (set-specific) message is shown and the flow stops (later steps, when
added, gate on ``found``). Table freshness (delay vs now; red if > 6h) is ALWAYS
reported as a data-quality indicator, whether or not a trend is found.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from rcalibrary.analyzers import analyzer
from rcalibrary.analyzers.context import AnalysisContext, AnalysisResult

FRESHNESS_THRESHOLD_HOURS = 6.0
USID_DATE_WINDOW_DAYS = 7  # match a trend on the USID within +/- this many days


def _parse_dt(value):
    try:
        return pd.to_datetime(value, utc=True, errors="coerce")
    except Exception:  # noqa: BLE001
        return pd.NaT


def _fmt(value) -> str:
    dt = _parse_dt(value)
    if pd.isna(dt):
        return "unknown"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


@analyzer("voc_collect_trend")
def voc_collect_trend(ctx: AnalysisContext) -> AnalysisResult:
    df = ctx.dataset
    group = ctx.inputs.get("_input_group")
    now = datetime.now(timezone.utc)

    # --- table freshness (always, as a data-quality indicator) ---------------
    if "last_update_time" in df.columns and len(df):
        last_update = _parse_dt(df["last_update_time"]).max()
    else:
        last_update = pd.NaT
    if pd.isna(last_update):
        delay_hours, delay_state, updated = None, "neutral", "unknown"
    else:
        delay_hours = round((now - last_update.to_pydatetime()).total_seconds() / 3600.0, 1)
        delay_state = "bad" if delay_hours > FRESHNESS_THRESHOLD_HOURS else "good"
        updated = _fmt(last_update)

    # --- trend lookup (branch on the chosen input set) -----------------------
    match = df.iloc[0:0]
    if group == "trend_id":
        tid = str(ctx.inputs.get("trend_id") or "").strip()
        if tid and "trend_id" in df.columns:
            match = df[df["trend_id"].astype(str) == tid]
    elif group == "usid_date":
        usid = str(ctx.inputs.get("usid") or "").strip()
        date = _parse_dt(ctx.inputs.get("date"))
        if usid and "usid" in df.columns:
            cand = df[df["usid"].astype(str) == usid].copy()
            if len(cand) and not pd.isna(date) and "trend_start_time" in cand.columns:
                # Add the distance as a column FIRST, then filter on it (filtering
                # via a separate Series + reassign can re-introduce rows on empty).
                cand["_dist"] = (_parse_dt(cand["trend_start_time"]) - date).abs()
                cand = cand[cand["_dist"] <= pd.Timedelta(days=USID_DATE_WINDOW_DAYS)]
                cand = cand.sort_values("_dist")
            match = cand

    found = len(match) > 0
    if found:
        row = match.iloc[0]
        trend_md = "\n".join(
            [
                f"**Trend ID:** {row.get('trend_id', '—')}",
                f"**USID:** {row.get('usid', '—')}",
                f"**Trend start time:** {_fmt(row.get('trend_start_time'))}",
                f"**Trend status:** {row.get('trend_status', '—')}",
                f"**Last update time:** {_fmt(row.get('last_update_time'))}",
            ]
        )
    elif group == "trend_id":
        trend_md = "**Trend not found.** Double-check the Trend ID and try again."
    elif group == "usid_date":
        trend_md = (
            "**No VoC trend was detected for this USID around the date provided.** "
            "Try a different USID or date."
        )
    else:
        trend_md = "No trend lookup was performed (no input set selected)."

    return AnalysisResult(
        summary={
            "found": found,
            "trend_md": trend_md,
            "delay_hours": delay_hours,
            "delay_state": delay_state,
            "table_updated": f"Table updated {updated}",
        }
    )
