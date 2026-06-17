"""Generate dummy `voc_trends.csv` for local testing of Step 1.

    python data/samples/ana.rca.netcare-voc-trend/generate_dummy.py

`last_update_time` is stamped relative to NOW, so freshly generated data shows
GREEN freshness; it turns RED once the delay exceeds 6h (re-run to refresh). The
trend rows are fixed so example inputs stay stable:

  trend_id mode : T-1001 (found) · T-9999 (not found)
  usid_date mode: USID 0123456 + date 2026-06-10 (-> T-1001) · 9999999 (not found)
"""

import csv
import pathlib
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
updated = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")  # ~green

ROWS = [
    {"trend_id": "T-1001", "usid": "0123456", "trend_start_time": "2026-06-10T14:00:00Z", "trend_status": "open"},
    {"trend_id": "T-1002", "usid": "0123456", "trend_start_time": "2026-05-02T09:00:00Z", "trend_status": "resolved"},
    {"trend_id": "T-2003", "usid": "0654321", "trend_start_time": "2026-06-12T22:00:00Z", "trend_status": "monitoring"},
    {"trend_id": "T-3004", "usid": "0789012", "trend_start_time": "2026-06-14T03:00:00Z", "trend_status": "open"},
]
for r in ROWS:
    r["last_update_time"] = updated

path = pathlib.Path(__file__).with_name("voc_trends.csv")
with path.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(
        fh, fieldnames=["trend_id", "usid", "trend_start_time", "trend_status", "last_update_time"]
    )
    writer.writeheader()
    writer.writerows(ROWS)
print(f"wrote {path} (last_update_time={updated})")
