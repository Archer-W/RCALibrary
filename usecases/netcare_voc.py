"""NetCare VoC Trend Triage — Step 1: collect trend information.

Registered as a plugin analyzer (`voc_collect_trend`). Owns the workflow LOGIC;
the data SOURCE is the swap point for the data agent (dummy CSV via the sample
provider now -> real Snowflake later). See
templates/ana.rca.netcare-voc-trend/IMPLEMENTATION.md.

Step 1 branches on the chosen input set (``_input_group``):
  * ``trend_id``  -> look up the trend by its USID-level Trend ID
  * ``usid_date`` -> look up the trend by USID near the provided date
Output (a ``fields`` panel — one box per value): Trend ID, USID, trend status
(color-coded: Active=red, Cooling=orange, Closed=blue), trend start time,
duration (how long the trend has been there), last update time. If not found, a
(set-specific) message is shown and the flow stops (later steps, when added,
gate on ``found``). Table freshness (delay vs now; red if > 6h) is ALWAYS
reported as a data-quality indicator, whether or not a trend is found.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pandas as pd

from rcalibrary.analyzers import analyzer
from rcalibrary.analyzers.context import AnalysisContext, AnalysisResult

FRESHNESS_THRESHOLD_HOURS = 6.0
USID_DATE_WINDOW_DAYS = 7  # match a trend on the USID within +/- this many days

# Trend status -> field/stat color state: Active=red, Cooling=orange, Closed=blue.
# Matched case-insensitively; anything else falls back to neutral (grey = no trend).
_STATUS_STATE = {
    "active": "bad",   # red — still impacting
    "cooling": "warn",  # orange — improving / settling
    "closed": "info",  # blue — resolved
}
# Same scheme in the table badge palette (red/amber/blue).
_STATUS_TONE = {"active": "red", "cooling": "amber", "closed": "blue"}


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


def _duration_str(start, end) -> str:
    """How long the trend has been there, in whole days (derived from the table's
    trend_start_time)."""
    start, end = _parse_dt(start), _parse_dt(end)
    if pd.isna(start) or pd.isna(end):
        return "unknown"
    days = max(0, (end - start).days)
    return f"{days} day" if days == 1 else f"{days} days"


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
    anchor = {"found": found}
    if found:
        row = match.iloc[0]
        status = str(row.get("trend_status") or "").strip()
        status_state = _STATUS_STATE.get(status.lower(), "neutral")
        # Anchor for later steps (Step 2 reads this via ctx.results["collect_trend"]).
        anchor = {
            "found": True,
            "usid": str(row.get("usid") or ""),
            "trend_id": str(row.get("trend_id") or ""),
            "trend_start_time": row.get("trend_start_time"),
            "trend_status": status,
            "last_update_time": row.get("last_update_time"),
        }
        # Duration = how long the trend has been there. Closed trends freeze at
        # their last update (a proxy for close time); live trends measure to now.
        end_ref = row.get("last_update_time") if status.lower() == "closed" else now
        # One box per value (see the `fields` panel); the status box is colored.
        trend_fields = {
            "items": [
                {"label": "Trend ID", "value": row.get("trend_id", "—")},
                {"label": "USID", "value": row.get("usid", "—")},
                {"label": "Trend status", "value": status or "—", "state": status_state},
                {"label": "Trend start time", "value": _fmt(row.get("trend_start_time"))},
                {
                    "label": "Duration",
                    "value": _duration_str(row.get("trend_start_time"), end_ref),
                    "sub": "since trend start",
                },
                {"label": "Last update time", "value": _fmt(row.get("last_update_time"))},
            ],
            "notice": None,
        }
    elif group == "trend_id":
        trend_fields = {
            "items": [],
            "notice": "**Trend not found.** Double-check the Trend ID and try again.",
        }
    elif group == "usid_date":
        trend_fields = {
            "items": [],
            "notice": (
                "**No VoC trend was detected for this USID around the date provided.** "
                "Try a different USID or date."
            ),
        }
    else:
        trend_fields = {"items": [], "notice": "No trend lookup was performed (no input set selected)."}

    return AnalysisResult(
        summary={
            "found": found,
            "anchor": anchor,  # consumed by Step 2 (not rendered directly)
            "trend_fields": trend_fields,
            "delay_hours": delay_hours,
            "delay_state": delay_state,
            "table_updated": f"Table updated {updated}",
        }
    )


# =============================================================================
# Step 2 — Neighbor trend correlation
# =============================================================================
# DUMMY/STUB. Owns the report CONTRACT (so the UI is testable now); the DATA
# AGENT replaces the query + the dedup/aggregation with real logic behind the
# same contract (search for "DATA AGENT" below). See IMPLEMENTATION.md.

NEIGHBOR_DEDUP_FACTOR = 0.85  # DATA AGENT: placeholder — real dedup is record-level.

# Each granularity: pandas resample freq + how many days before the first trend
# start the window opens. The window ALWAYS ends at "now" (never in the future).
_GRANS = [
    {"key": "daily", "label": "Daily", "freq": "D", "back": 30},
    {"key": "3h", "label": "3-hourly", "freq": "3h", "back": 7},
    {"key": "hourly", "label": "Hourly", "freq": "h", "back": 3},
]


def _has_active(frame) -> bool:
    """True if any row's trend_status is Active (case-insensitive)."""
    if "trend_status" not in getattr(frame, "columns", []) or not len(frame):
        return False
    return bool((frame["trend_status"].astype(str).str.lower() == "active").any())


def _empty_ts(notice: str) -> dict:
    return {
        "default_granularity": "daily",
        "granularities": [{"key": g["key"], "label": g["label"]} for g in _GRANS],
        "windows": {},
        "series": [],
        "y_title": "Care call volume",
        "notice": notice,
    }


@analyzer("voc_neighbor_correlation")
def voc_neighbor_correlation(ctx: AnalysisContext) -> AnalysisResult:
    """Retrieve the searched USID's care-call-volume timeseries plus neighbor
    USIDs that have correlated trends. Reads Step 1's confirmed anchor
    (``ctx.results["collect_trend"]``) and two pulls: ``neighbors``
    (``ctx.dataset``) + ``call_volume`` (``ctx.datasets["call_volume"]``)."""
    now = pd.Timestamp(datetime.now(timezone.utc))
    prior = ctx.results.get("collect_trend")
    anchor = (prior.summary.get("anchor") if prior else None) or {}
    if not anchor.get("found"):
        return AnalysisResult(summary={"found": False, "volume_ts": _empty_ts("No confirmed trend.")})

    anchor_usid = str(anchor.get("usid") or "")
    # The searched USID's own trend counts toward "is any cluster trend Active",
    # independent of whether the neighbors query re-includes the anchor's row.
    anchor_active = str(anchor.get("trend_status") or "").strip().lower() == "active"
    neighbors = ctx.dataset
    volume = ctx.datasets.get("call_volume")

    # --- correlated trends for this anchor (DATA AGENT: filter in SQL) --------
    if anchor_usid and "anchor_usid" in neighbors.columns:
        corr = neighbors[neighbors["anchor_usid"].astype(str) == anchor_usid].copy()
    else:
        corr = neighbors.iloc[0:0].copy()
    if not len(corr):
        return AnalysisResult(
            summary={
                "found": True,
                "empty_notice": "No correlated neighbor trends were found for this USID.",
                "cluster_active": anchor_active,  # no neighbors -> just the anchor's status
                "volume_ts": _empty_ts("No correlated neighbor trends were found for this USID."),
            }
        )

    corr["_start"] = _parse_dt(corr["trend_start_time"])
    if "trend_end_time" in corr.columns:
        corr["_end"] = _parse_dt(corr["trend_end_time"])
    else:
        corr["_end"] = pd.Series(pd.NaT, index=corr.index, dtype="datetime64[ns, UTC]")
    corr["_end"] = corr["_end"].fillna(now)  # ongoing (Active/Cooling) -> now
    corr = corr.sort_values(["distance_km", "_start"])  # anchor (distance 0) first

    # --- correlated-trends table ---------------------------------------------
    table = [
        {
            "Trend ID": str(r.get("trend_id") or ""),
            "USID": str(r.get("usid") or ""),
            "Trend status": _badge(
                str(r.get("trend_status") or "—").strip() or "—",
                _STATUS_TONE.get(str(r.get("trend_status") or "").strip().lower(), "grey"),
            ),
            "Trend start": _fmt(r.get("trend_start_time")),
            "Duration": _duration_str(r.get("trend_start_time"), r["_end"]),
            "Distance (km)": round(float(r.get("distance_km") or 0.0), 1),
            "Location type": str(r.get("location_type") or "—"),
        }
        for _, r in corr.iterrows()
    ]

    # --- per-granularity windows + time grids (per the spec's rules) ---------
    first_start, last_end = corr["_start"].min(), corr["_end"].max()
    if pd.isna(first_start) or pd.isna(last_end):
        # No usable trend timestamps -> can't build windows; keep the table.
        return AnalysisResult(
            summary={
                "found": True,
                "cluster_active": anchor_active or _has_active(corr),
                "volume_ts": _empty_ts("Correlated trends have no usable start times."),
            },
            table=table,
        )
    grids, windows = {}, {}
    for g in _GRANS:
        start = (first_start - pd.Timedelta(days=g["back"])).floor(g["freq"])
        end = now  # x-axis ends at the present — never in the future
        grids[g["key"]] = pd.date_range(start, end, freq=g["freq"])
        windows[g["key"]] = {"start": start.isoformat(), "end": end.isoformat()}

    # --- per-USID call-volume series, resampled to each granularity ----------
    vol = volume.copy() if volume is not None else pd.DataFrame(columns=["usid", "timestamp", "call_volume"])
    if len(vol):
        vol["_ts"] = _parse_dt(vol["timestamp"])
        vol["usid"] = vol["usid"].astype(str)

    usids = list(dict.fromkeys(str(u) for u in corr["usid"]))  # unique, anchor first
    agg = {g["key"]: None for g in _GRANS}
    series = []
    for usid in usids:
        rows = vol[vol["usid"] == usid] if len(vol) else vol
        role = "anchor" if usid == anchor_usid else "neighbor"
        by_gran = {}
        for g in _GRANS:
            grid = grids[g["key"]]
            if len(rows):
                s = rows.set_index("_ts")["call_volume"].astype(float).sort_index()
                s = s.resample(g["freq"]).sum().reindex(grid).fillna(0.0)
            else:
                s = pd.Series(0.0, index=grid)
            by_gran[g["key"]] = {"x": [t.isoformat() for t in grid], "y": [float(v) for v in s.values]}
            agg[g["key"]] = s.values if agg[g["key"]] is None else agg[g["key"]] + s.values
        label = f"{usid} (searched)" if role == "anchor" else usid
        series.append({"usid": usid, "label": label, "role": role, "by_gran": by_gran})

    # --- aggregated (deduplicated) line --------------------------------------
    # DATA AGENT: real dedup is record-level (a call linked to >1 trend counted
    # once). Placeholder: a capped sum across USIDs.
    agg_series = {"usid": "__aggregate__", "label": "Aggregated (dedup)", "role": "aggregate", "by_gran": {}}
    for g in _GRANS:
        grid = grids[g["key"]]
        vals = agg[g["key"]] if agg[g["key"]] is not None else [0.0] * len(grid)
        agg_series["by_gran"][g["key"]] = {
            "x": [t.isoformat() for t in grid],
            "y": [round(float(v) * NEIGHBOR_DEDUP_FACTOR, 2) for v in vals],
        }
    series.append(agg_series)

    volume_ts = {
        "default_granularity": "daily",
        "granularities": [{"key": g["key"], "label": g["label"]} for g in _GRANS],
        "windows": windows,
        "series": series,
        # earliest trend start -> latest trend end (ongoing trends end at now)
        "trend_span": {"start": first_start.isoformat(), "end": last_end.isoformat()},
        "y_title": "Care call volume",
        "notice": None,
    }

    # --- call totals within the anomaly window (Trend-panel boxes + the map) --
    if len(vol):
        w = vol[(vol["_ts"] >= first_start) & (vol["_ts"] <= last_end)].copy()
        w["_cv"] = pd.to_numeric(w["call_volume"], errors="coerce").fillna(0.0)
        per_usid_win = {str(u): int(round(float(v))) for u, v in w.groupby("usid")["_cv"].sum().items()}
    else:
        per_usid_win = {}
    searched_calls = int(per_usid_win.get(anchor_usid, 0))
    cluster_total = sum(per_usid_win.get(u, 0) for u in usids)
    cluster_dedup_calls = int(round(cluster_total * NEIGHBOR_DEDUP_FACTOR))
    cluster_meta = {}  # usid -> {status, start, close}; anchor first wins on dup USID
    for _, r in corr.iterrows():
        u = str(r.get("usid") or "")
        if u in cluster_meta:
            continue
        end_raw = r.get("trend_end_time")
        cluster_meta[u] = {
            "status": str(r.get("trend_status") or ""),
            "start": r.get("trend_start_time"),
            "close": None if pd.isna(_parse_dt(end_raw)) else end_raw,  # None => ongoing
        }

    return AnalysisResult(
        summary={
            "found": True,
            "volume_ts": volume_ts,
            "cluster_usids": usids,  # anchor + correlated neighbors (Step 3 chains on this)
            # any cluster trend (anchor incl.) still Active — drives Step 3's alert
            "cluster_active": anchor_active or _has_active(corr),
            # for the map (Step 4) + the Trend-panel call-total boxes
            "trend_span": volume_ts["trend_span"],
            "cluster_meta": cluster_meta,             # usid -> {status, start, close}
            "usid_window_calls": per_usid_win,        # usid -> calls in the window
            "cluster_total_calls": cluster_dedup_calls,
            "field_overlay": {  # appended into the Step-1 Trend fields panel
                "after_label": "Trend status",
                "items": [
                    {"label": "Calls on searched USID", "value": searched_calls, "sub": "in the trend window"},
                    {"label": "Cluster calls (dedup)", "value": cluster_dedup_calls, "sub": "all correlated USIDs"},
                ],
            },
        },
        table=table,  # rendered by the `table` panel (neighbor_table)
    )


# =============================================================================
# Step 3 — Known network-event search & ranking (associated tickets)
# =============================================================================
# DUMMY/STUB. Owns the report CONTRACT; the DATA AGENT replaces the query +
# scoring with real logic (search "DATA AGENT" below). Rendered by the `table`
# panel: a cell can be a plain value OR a {"value", "tone"} badge for color-coding.

# Colored-badge tones the `table` panel understands: red/amber/green/blue/grey/purple.
_TICKET_TYPE_TONE = {  # categorical by ticket type
    "outage": "red",
    "maintenance": "blue",
    "alarm": "amber",
    "alarms": "amber",
    "congestion": "purple",
}
_IMPACT_TONE = {"high": "red", "medium": "amber", "low": "green"}

# Display order = the requested columns (also the `encoding.columns` in the template).
TICKET_COLUMNS = [
    "Ticket ID", "Ticket type", "Event name", "USID", "Trend dist (km)",
    "Event start", "Event end", "PRT", "Status", "Confidence", "Impact",
]


def _badge(value, tone):
    return {"value": value, "tone": tone}


def _conf_tone(pct: int) -> str:
    # Takes the SAME rounded percent shown on the badge, so the number and the
    # color can never disagree at a threshold (e.g. 69.6% -> "70%" stays amber).
    return "green" if pct >= 70 else "amber" if pct >= 40 else "grey"


def _dist_tone(km: float) -> str:
    # 0 km (in the trend cluster) = green; nearby 2-hop = amber; far = grey.
    return "green" if km <= 0 else "amber" if km <= 5 else "grey"


def _fmt_opt(value) -> str:
    """Format a timestamp, or '—' when missing (e.g. PRT/end on ongoing tickets)."""
    return _fmt(value) if not pd.isna(_parse_dt(value)) else "—"


@analyzer("voc_ticket_search")
def voc_ticket_search(ctx: AnalysisContext) -> AnalysisResult:
    """List tickets/events associated to the trend cluster (each cluster USID +
    their 2-hop neighbors), ranked by association confidence. Reads Step 1's
    anchor and Step 2's ``cluster_usids``; ``ctx.dataset`` = the ``tickets`` pull."""
    prior = ctx.results.get("collect_trend")
    anchor = (prior.summary.get("anchor") if prior else None) or {}
    if not anchor.get("found"):
        return AnalysisResult(summary={"found": False}, table=[])
    anchor_usid = str(anchor.get("usid") or "")

    # The trend cluster (anchor + correlated neighbors) from Step 2. DATA AGENT:
    # expand these to their 2-hop topology neighbors and query tickets for the
    # full USID set, returning a per-ticket association confidence. The dummy
    # pre-associates tickets by anchor_usid, so the stub just filters on that.
    step2 = ctx.results.get("neighbor_correlation")
    cluster = (step2.summary.get("cluster_usids") if step2 else None) or [anchor_usid]
    cluster_set = {str(u) for u in cluster}  # trend-cluster USIDs (distance 0)
    cluster_active = bool(step2.summary.get("cluster_active")) if step2 else False
    now = pd.Timestamp(datetime.now(timezone.utc))

    tickets = ctx.dataset
    if anchor_usid and "anchor_usid" in tickets.columns:
        df = tickets[tickets["anchor_usid"].astype(str) == anchor_usid].copy()
    else:
        df = tickets.iloc[0:0].copy()
    if not len(df):
        return AnalysisResult(
            summary={
                "found": True,
                "empty_notice": "No known network events were associated to this cluster.",
                # header boxes: no ticket -> no identifiable root cause / PRT
                "rc_value": "—", "rc_sub": "no matching ticket", "rc_state": "neutral",
                "rc_badge": None, "rc_detail": None,
                "prt_value": "missing", "prt_sub": "no PRT (no ticket)", "prt_state": "neutral",
            },
            table=[],
        )

    df["_conf"] = pd.to_numeric(df.get("assoc_confidence"), errors="coerce").fillna(0.0)
    df = df.sort_values("_conf", ascending=False)  # rank by confidence desc

    rows = []
    overlay = []  # compact per-ticket data the timeseries panel overlays on click
    for _, r in df.iterrows():
        tid = str(r.get("ticket_id") or "").strip()
        ttype = str(r.get("ticket_type") or "").strip()
        status = str(r.get("ticket_status") or "").strip()
        impact = str(r.get("projected_impact") or "").strip()
        ename = str(r.get("event_name") or "—")
        pct = round(float(r["_conf"]) * 100)
        # Distance to the trend: 0 if the ticket's USID is in the cluster, else
        # the distance to the nearest cluster USID. DATA AGENT: compute the real
        # geo distance; the dummy carries it in `dist_to_trend_km`.
        usid = str(r.get("usid") or "")
        if usid in cluster_set:
            dist_km = 0.0
        else:
            d = pd.to_numeric(r.get("dist_to_trend_km"), errors="coerce")
            dist_km = 0.0 if pd.isna(d) else float(d)
        dist_txt = "0" if dist_km == 0 else f"{round(dist_km, 1)}"
        type_tone = _TICKET_TYPE_TONE.get(ttype.lower(), "grey")
        status_tone = "amber" if status.lower() == "open" else "grey"
        impact_tone = _IMPACT_TONE.get(impact.lower(), "grey")
        conf_tone = _conf_tone(pct)
        rows.append(
            {
                "Ticket ID": tid or "—",
                "Ticket type": _badge(ttype or "—", type_tone),
                "Event name": ename,
                "USID": usid or "—",
                "Trend dist (km)": _badge(dist_txt, _dist_tone(dist_km)),
                "Event start": _fmt_opt(r.get("event_start_time")),
                "Event end": _fmt_opt(r.get("event_end_time")),
                "PRT": _fmt_opt(r.get("prt")),
                "Status": _badge(status or "—", status_tone),
                "Confidence": _badge(f"{pct}%", conf_tone),
                "Impact": _badge(impact or "—", impact_tone),
            }
        )
        # Overlay: start/end (ISO) position the band; the rest are structured
        # fields the frontend composes into a color-coded tag. No time in the tag
        # (the band's range shows it). Blank CSV cells parse as NaN -> normalize.
        start_raw = r.get("event_start_time")
        start_raw = None if pd.isna(_parse_dt(start_raw)) else start_raw
        end_raw = r.get("event_end_time")
        end_raw = None if pd.isna(_parse_dt(end_raw)) else end_raw
        prt_raw = r.get("prt")
        prt_raw = None if pd.isna(_parse_dt(prt_raw)) else prt_raw
        overlay.append({
            "id": tid,
            "tone": conf_tone,  # confidence -> band fill + tag background/border
            "start": start_raw,
            "end": end_raw,
            "prt": prt_raw,
            "usid": usid or "—",
            "type": ttype or "—",
            "type_tone": type_tone,
            "dist": dist_txt,
            "status": status or "—",
            "status_tone": status_tone,
            "impact": impact or "—",
            "impact_tone": impact_tone,
            "event": ename,
        })
    # Header boxes: the top ticket (highest confidence) as the likely root cause
    # + its planned restore time (PRT). df is already sorted by confidence desc.
    top = df.iloc[0]
    t_pct = round(float(top["_conf"]) * 100)
    t_type = str(top.get("ticket_type") or "—").strip() or "—"
    t_event = str(top.get("event_name") or "—")
    t_id = str(top.get("ticket_id") or "—").strip() or "—"
    rc_value = f"{t_pct}%"
    rc_badge = t_id                      # the root-cause ticket number (highlighted pill)
    rc_detail = t_event                  # the event name (prominent, not muted)
    rc_sub = f"{t_type} · {t_pct}% confidence"
    rc_state = "good" if t_pct >= 70 else "warn" if t_pct >= 40 else "neutral"
    prt_alert = None
    prt_dt = _parse_dt(top.get("prt"))
    if pd.isna(prt_dt):
        prt_value, prt_state, prt_sub = "missing", "neutral", "no PRT on the top ticket"
    elif prt_dt < now:  # planned restore time already passed -> expired
        prt_value, prt_state = prt_dt.strftime("%b %d, %H:%M"), "bad"
        if cluster_active:  # escalate: overdue restore while a cluster trend is Active
            prt_alert, prt_sub = "⚠️ EXPIRED — TREND ACTIVE", None
        else:
            prt_sub = "expired (past due)"
    else:
        prt_value, prt_state = prt_dt.strftime("%b %d, %H:%M"), "neutral"
        prt_sub = f"from {str(top.get('ticket_id') or 'top ticket')} (UTC)"

    return AnalysisResult(
        summary={
            "found": True,
            "ticket_count": len(rows),
            "ticket_overlay": overlay,
            "rc_value": rc_value, "rc_sub": rc_sub, "rc_state": rc_state,
            "rc_badge": rc_badge, "rc_detail": rc_detail,
            "prt_value": prt_value, "prt_sub": prt_sub, "prt_state": prt_state, "prt_alert": prt_alert,
        },
        table=rows,
    )


# =============================================================================
# Map layer — neighborhood map of the trend cluster, tickets & nearby sites
# =============================================================================
# DUMMY/STUB. The DATA AGENT swaps `voc_sites` for real site inventory (lat/lon)
# and the 3 km rule for real topology. Output: a `map` panel (offline lat/lon
# scatter by default; OSM tiles when enabled). See IMPLEMENTATION.md.

NEIGHBOR_RADIUS_KM = 3.0  # include no-trend sites within this many km of a trend/ticket site
_STATUS_MARKER = {  # trend status -> (marker hex, field/stat state)
    "active": ("#c0392b", "bad"),    # red
    "cooling": ("#e0892e", "warn"),  # orange
    "closed": ("#0568AE", "info"),   # blue
}
_NO_TREND_MARKER = ("#475569", "neutral")  # dark slate — any no-trend site (tickets shown by the red centre mark)
_MAP_LEGEND = [
    {"label": "Active", "color": "#c0392b"},
    {"label": "Cooling", "color": "#e0892e"},
    {"label": "Closed", "color": "#0568AE"},
    {"label": "No trend", "color": "#475569"},
]


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _ticket_in_window(t: dict, span: dict) -> bool:
    ws, we = _parse_dt(span.get("start")), _parse_dt(span.get("end"))
    if pd.isna(ws) or pd.isna(we):
        return True
    ts = _parse_dt(t.get("start"))
    if pd.isna(ts):
        return True
    te = _parse_dt(t.get("end"))
    if pd.isna(te):
        te = we  # ongoing -> through the window end
    return (ts <= we) and (te >= ws)


@analyzer("voc_map_build")
def voc_map_build(ctx: AnalysisContext) -> AnalysisResult:
    """Build the neighborhood map: cluster sites (colored by trend status), ticket
    sites, and no-trend sites within 3 km. Chains on Steps 1-3 and reads the
    ``site_inventory`` pull (ctx.dataset). DATA AGENT: real inventory + topology."""
    prior = ctx.results.get("collect_trend")
    anchor = (prior.summary.get("anchor") if prior else None) or {}
    if not anchor.get("found"):
        return AnalysisResult(summary={"found": False, "map_data": {"features": [], "notice": "No confirmed trend."}})

    step2, step3 = ctx.results.get("neighbor_correlation"), ctx.results.get("ticket_search")
    s2 = (step2.summary if step2 else {}) or {}
    s3 = (step3.summary if step3 else {}) or {}
    cluster_usids = [str(u) for u in (s2.get("cluster_usids") or [])]
    cluster_meta = s2.get("cluster_meta") or {}  # usid -> {status, start, close}
    win_calls = s2.get("usid_window_calls") or {}
    trend_span = s2.get("trend_span") or {}
    overlay = s3.get("ticket_overlay") or []

    # site inventory: usid -> (lat, lon)  (DATA AGENT: real inventory CSV/query)
    sites = ctx.dataset
    inv: dict[str, tuple] = {}
    if sites is not None and "usid" in getattr(sites, "columns", []):
        for _, srow in sites.iterrows():
            lat = pd.to_numeric(srow.get("lat"), errors="coerce")
            lon = pd.to_numeric(srow.get("lon"), errors="coerce")
            inv[str(srow.get("usid"))] = (
                None if pd.isna(lat) else float(lat),
                None if pd.isna(lon) else float(lon),
            )

    features: dict[str, dict] = {}

    def _add(usid: str, role: str, meta):
        lat, lon = inv.get(usid, (None, None))
        meta = meta or {}
        status = str(meta.get("status") or "").strip()
        color, state = _STATUS_MARKER.get(status.lower(), _NO_TREND_MARKER) if status else _NO_TREND_MARKER
        features[usid] = {
            "usid": usid, "lat": lat, "lon": lon, "role": role,
            "trend_status": status or None,
            "trend_start": meta.get("start"),
            "trend_close": meta.get("close"),
            "color": color, "color_state": state,
            "total_calls": int(win_calls.get(usid, 0)),
            "calls_known": usid in win_calls,  # distinguish genuine 0 from "no data"
            "tickets": [],
        }

    for u in cluster_usids:  # (a) trend cluster sites, colored by status
        _add(u, "cluster", cluster_meta.get(u))
    for t in overlay:  # (b) ticket sites whose event overlaps the anomaly window
        u = str(t.get("usid") or "")
        if not u or not _ticket_in_window(t, trend_span):
            continue
        if u not in features:
            _add(u, "ticket", cluster_meta.get(u))
        features[u]["tickets"].append(t)
    # (c) no-trend sites within 3 km of any trend/ticket site. A site is mappable
    # only when BOTH coordinates are present (a partial coord = off-map).
    def _xy(f):
        return f["lat"] is not None and f["lon"] is not None

    anchored = [(f["lat"], f["lon"]) for f in features.values() if _xy(f)]
    for usid, (lat, lon) in inv.items():
        if usid in features or lat is None or lon is None:
            continue
        if any(_haversine_km(lat, lon, la, lo) <= NEIGHBOR_RADIUS_KM for la, lo in anchored):
            _add(usid, "neighbor", None)

    feats = list(features.values())
    pts = [(f["lat"], f["lon"]) for f in feats if _xy(f)]
    center = (
        {"lat": sum(p[0] for p in pts) / len(pts), "lon": sum(p[1] for p in pts) / len(pts)}
        if pts else None
    )
    map_data = {
        "features": feats,
        "trend_span": trend_span,
        "cluster_total_calls": int(s2.get("cluster_total_calls") or 0),
        "center": center,
        "radius_km": NEIGHBOR_RADIUS_KM,
        "legend": _MAP_LEGEND,
        "missing_coords": sum(1 for f in feats if not _xy(f)),
        "notice": "No sites to map." if not feats else (None if center else "No sites have coordinates to map."),
    }
    return AnalysisResult(summary={"found": True, "map_data": map_data})
