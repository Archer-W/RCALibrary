"""Generate dummy CSVs for local testing of the NetCare VoC Trend Triage.

    python data/samples/ana.rca.netcare-voc-trend/generate_dummy.py

Writes three datasets:
  * voc_trends.csv       — Step 1 trend look-up (one row per trend).
  * voc_neighbors.csv     — Step 2 correlated trends, keyed by anchor_usid.
  * voc_call_volume.csv   — Step 2 hourly care-call volume per USID.

`last_update_time` is stamped relative to NOW, so freshly generated data shows
GREEN freshness; it turns RED once the delay exceeds 6h (re-run to refresh). Trend
rows use FIXED dates so example inputs stay stable:

  trend_id mode : T-1001 (found) · T-9999 (not found)
  usid_date mode: USID 0123456 + date 2026-06-10 (-> T-1001) · 9999999 (not found)
  Step 2 demo   : T-1001 / USID 0123456 -> 3 correlated neighbor USIDs.
"""

import csv
import math
import pathlib
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).parent
now = datetime.now(timezone.utc)
updated = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")  # ~green


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _write(name: str, fieldnames: list[str], rows: list[dict]) -> None:
    path = HERE / name
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


# --- voc_trends (Step 1) -----------------------------------------------------
# trend_status drives the colored status box: Active=red, Cooling=orange, Closed=grey.
TRENDS = [
    {"trend_id": "T-1001", "usid": "0123456", "trend_start_time": "2026-06-10T14:00:00Z", "trend_status": "Active"},
    {"trend_id": "T-1002", "usid": "0123456", "trend_start_time": "2026-05-02T09:00:00Z", "trend_status": "Closed"},
    {"trend_id": "T-2003", "usid": "0654321", "trend_start_time": "2026-06-12T22:00:00Z", "trend_status": "Cooling"},
    {"trend_id": "T-3004", "usid": "0789012", "trend_start_time": "2026-06-14T03:00:00Z", "trend_status": "Active"},
]
for r in TRENDS:
    r["last_update_time"] = updated
_write("voc_trends.csv", ["trend_id", "usid", "trend_start_time", "trend_status", "last_update_time"], TRENDS)


# --- voc_neighbors (Step 2) --------------------------------------------------
# Correlated trends per anchor_usid. The anchor's OWN trend is included with
# distance_km = 0 (so it sorts first). trend_end_time blank = ongoing.
NEIGHBORS = [
    # anchor 0123456 (the T-1001 / usid_date demo): 3 correlated neighbors
    ("0123456", "T-1001", "0123456", "2026-06-10T14:00:00Z", "",                     "Active",  0.0, "urban"),
    ("0123456", "N-2001", "0223456", "2026-06-11T06:00:00Z", "",                     "Active",  1.2, "urban"),
    ("0123456", "N-2002", "0323456", "2026-06-08T00:00:00Z", "2026-06-16T00:00:00Z", "Cooling", 3.5, "suburban"),
    ("0123456", "N-2003", "0423456", "2026-06-05T00:00:00Z", "2026-06-14T00:00:00Z", "Closed",  7.8, "rural"),
    # anchor 0654321 (T-2003): one neighbor
    ("0654321", "T-2003", "0654321", "2026-06-12T22:00:00Z", "2026-06-17T00:00:00Z", "Cooling", 0.0, "urban"),
    ("0654321", "N-3001", "0654322", "2026-06-13T10:00:00Z", "",                     "Active",  2.1, "suburban"),
    # anchor 0789012 (T-3004): anchor only, no correlated neighbors
    ("0789012", "T-3004", "0789012", "2026-06-14T03:00:00Z", "",                     "Active",  0.0, "rural"),
]
NEIGHBOR_COLS = [
    "anchor_usid", "trend_id", "usid", "trend_start_time", "trend_end_time",
    "trend_status", "distance_km", "location_type",
]
_write("voc_neighbors.csv", NEIGHBOR_COLS, [dict(zip(NEIGHBOR_COLS, row)) for row in NEIGHBORS])


# --- voc_call_volume (Step 2) ------------------------------------------------
# Hourly care-call volume per USID, from GEN_START to now. Each series = daily
# seasonality (peaks midday) + a sustained surge during that USID's trend window,
# so the trend is visible. The analyzer resamples this to daily/3h/hourly.
GEN_START = datetime(2026, 5, 1, tzinfo=timezone.utc)

# Per-USID trend window (min start, max end-or-now) derived from NEIGHBORS.
def _parse(s: str):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if s else None

usid_window: dict[str, list] = {}
for row in NEIGHBORS:
    _, _, usid, start, end, *_ = row
    s, e = _parse(start), (_parse(end) or now)
    if usid not in usid_window:
        usid_window[usid] = [s, e]
    else:
        usid_window[usid][0] = min(usid_window[usid][0], s)
        usid_window[usid][1] = max(usid_window[usid][1], e)

vol_rows = []
hours = int((now - GEN_START).total_seconds() // 3600)
for usid, (w_start, w_end) in usid_window.items():
    # deterministic per-USID base level (no randomness — reproducible CSVs)
    base = 12 + (sum(ord(c) for c in usid) % 7)
    for h in range(hours + 1):
        t = GEN_START + timedelta(hours=h)
        season = 8.0 * math.sin(2 * math.pi * ((t.hour / 24.0) - 0.25))  # midday peak
        weekly = 3.0 * math.sin(2 * math.pi * (t.weekday() / 7.0))
        surge = 18.0 if w_start <= t <= w_end else 0.0
        volume = max(0, round(base + season + weekly + surge))
        vol_rows.append({"usid": usid, "timestamp": _iso(t), "call_volume": volume})
_write("voc_call_volume.csv", ["usid", "timestamp", "call_volume"], vol_rows)


# --- voc_tickets (Step 3) ----------------------------------------------------
# Tickets/events associated to the trend cluster (cluster USIDs + their 2-hop
# neighbors), keyed by anchor_usid. hop = 0 (searched) / 1 (correlated neighbor)
# / 2 (2-hop). assoc_confidence in [0,1]; the analyzer ranks by it descending and
# color-codes type / status / confidence / impact.
# dist_to_trend_km: distance from the ticket's USID to the nearest trend-cluster
# USID. 0 for cluster members (hop 0/1); a real value for 2-hop USIDs (hop 2).
TICKET_COLS = [
    "ticket_id", "anchor_usid", "usid", "hop", "dist_to_trend_km", "ticket_type", "event_name",
    "event_start_time", "event_end_time", "prt", "ticket_status",
    "assoc_confidence", "projected_impact",
]
# One PRT in the future (relative to now) so a non-expired PRT is demoable; the
# fixed-date PRTs below are in the past, so they show as expired.
future_prt = (now + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
TICKETS = [
    ("TKT-1001", "0123456", "0123456", 0, 0.0,  "Outage",      "Fiber cut – metro ring 12",     "2026-06-10T13:00:00Z", "2026-06-11T02:00:00Z", "2026-06-11T04:00:00Z", "open",   0.95, "High"),
    ("TKT-1002", "0123456", "0123456", 0, 0.0,  "Alarm",       "RSRP degradation cluster",      "2026-06-10T12:00:00Z", "",                     "",                     "open",   0.81, "Medium"),
    ("TKT-1003", "0123456", "0223456", 1, 0.0,  "Maintenance", "Planned SW upgrade – gNB",      "2026-06-09T01:00:00Z", "2026-06-09T05:00:00Z", "2026-06-09T05:00:00Z", "closed", 0.78, "Low"),
    ("TKT-1004", "0123456", "0999003", 2, 9.5,  "Outage",      "Backhaul link flap",            "2026-06-12T15:00:00Z", "2026-06-12T16:30:00Z", "2026-06-12T18:00:00Z", "open",   0.71, "Medium"),
    ("TKT-1005", "0123456", "0323456", 1, 0.0,  "Outage",      "Commercial power loss – site",  "2026-06-08T22:00:00Z", "2026-06-09T06:00:00Z", "2026-06-09T07:00:00Z", "closed", 0.64, "High"),
    ("TKT-1006", "0123456", "0423456", 1, 0.0,  "Congestion",  "PRB utilization saturation",    "2026-06-11T08:00:00Z", "",                     "",                     "open",   0.58, "Medium"),
    ("TKT-1007", "0123456", "0999001", 2, 11.2, "Maintenance", "Transport ring maintenance",    "2026-06-07T00:00:00Z", "2026-06-07T03:00:00Z", "2026-06-07T03:00:00Z", "closed", 0.42, "Low"),
    ("TKT-1008", "0123456", "0999002", 2, 3.2,  "Alarm",       "VSWR threshold alarm",          "2026-06-12T09:00:00Z", "",                     "",                     "open",   0.33, "Low"),
    # anchor 0654321 (T-2003)
    ("TKT-2001", "0654321", "0654321", 0, 0.0,  "Outage",      "Sector down – carrier 2",       "2026-06-12T20:00:00Z", "",                     future_prt,             "open",   0.88, "High"),
    ("TKT-2002", "0654321", "0654322", 1, 0.0,  "Maintenance", "Antenna re-tilt window",        "2026-06-11T02:00:00Z", "2026-06-11T04:00:00Z", "2026-06-11T04:00:00Z", "closed", 0.51, "Low"),
    # anchor 0789012 (T-3004)
    ("TKT-3001", "0789012", "0789012", 0, 0.0,  "Alarm",       "Cell availability drop",        "2026-06-14T02:00:00Z", "",                     "",                     "open",   0.69, "Medium"),
]
_write("voc_tickets.csv", TICKET_COLS, [dict(zip(TICKET_COLS, row)) for row in TICKETS])


# --- voc_sites (map layer) ---------------------------------------------------
# DATA AGENT: real site inventory (each USID -> lat/lon) replaces this dummy.
# lat/lon for every USID in voc_neighbors + voc_tickets, plus a few NO-TREND
# sites (0150xxx) within ~3 km of 0123456 so the "neighbors within 3 km" layer
# is demonstrable. ~0.009 deg latitude ≈ 1 km. Base ≈ Dallas, TX.
SITES = [
    # anchor 0123456 cluster — scattered in 2D (varied bearings/distances)
    ("0123456", 32.7800, -96.8000),  # anchor
    ("0223456", 32.7880, -96.7930),  # ~1.1 km NE
    ("0323456", 32.7600, -96.8250),  # ~3.2 km SW
    ("0423456", 32.7950, -96.7150),  # ~8 km E
    # 2-hop ticket USIDs for anchor 0123456 (different directions)
    ("0999002", 32.8080, -96.7950),  # ~3.1 km N (ticket)
    ("0999003", 32.7100, -96.7300),  # ~9.5 km SE (ticket)
    ("0999001", 32.8700, -96.8900),  # ~13 km NW (ticket)
    # other anchors' sites
    ("0654321", 32.9200, -96.6800),
    ("0654322", 32.9250, -96.6750),
    ("0789012", 32.6800, -96.9200),
    # NO-TREND sites within ~3 km of 0123456 (grey background layer), spread in 2D
    ("0150001", 32.7850, -96.7950),  # ~0.7 km NE
    ("0150002", 32.7740, -96.8060),  # ~0.9 km SW
    ("0150003", 32.7770, -96.7920),  # ~0.8 km SE
    ("0150004", 32.7890, -96.8080),  # ~1.2 km NW
]
_write("voc_sites.csv", ["usid", "lat", "lon"], [dict(zip(["usid", "lat", "lon"], s)) for s in SITES])

print(f"done (last_update_time={updated})")
