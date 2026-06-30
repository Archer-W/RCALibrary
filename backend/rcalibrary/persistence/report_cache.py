"""File-based cache of *saved* reports.

A saved report is the user's customized report (added library panels + their
order/sizes + removals), stored as a JSON blob keyed by the search inputs. When
the same key is searched again, the saved report is returned without recompute.

Deliberately simple (stdlib only, one JSON file per key) so it works offline,
needs no external service, and is easy to inspect or clear. The blob is opaque to
the backend (assembled client-side); it is re-validated as a ReportPayload only
when served back on /run.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_BYTES = 4 * 1024 * 1024  # 4 MiB — guard against unbounded client blobs


def _safe_dir(name: str) -> str:
    cleaned = _SAFE.sub("_", name)
    # the sanitizer (not route ordering) is the security boundary: never let a
    # component be empty or a dot-traversal (".", "..").
    return "_" if cleaned in ("", ".", "..") else cleaned


class ReportCacheError(ValueError):
    """A saved report could not be cached (e.g. it exceeds the size limit)."""


class ReportCache:
    def __init__(self, cache_dir: Path, max_bytes: int = _MAX_BYTES):
        self.cache_dir = Path(cache_dir)
        self.max_bytes = max_bytes

    @staticmethod
    def key(template_id: str, input_group: str | None, inputs: dict[str, Any], scope: str = "") -> str:
        # `scope` folds in the template version + principal so a template change
        # invalidates stale saves and saved reports are isolated per tenant.
        raw = json.dumps(
            {"t": template_id, "g": input_group, "i": inputs, "s": scope}, sort_keys=True, default=str
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _path(self, template_id: str, key: str) -> Path:
        return self.cache_dir / _safe_dir(template_id) / f"{key}.json"

    def get(self, template_id, input_group, inputs, scope: str = "") -> dict | None:
        path = self._path(template_id, self.key(template_id, input_group, inputs, scope))
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return None

    def put(self, template_id, input_group, inputs, report: dict, scope: str = "") -> str:
        blob = json.dumps(report, default=str)
        if len(blob.encode("utf-8")) > self.max_bytes:
            raise ReportCacheError(f"saved report exceeds the {self.max_bytes}-byte cache limit")
        key = self.key(template_id, input_group, inputs, scope)
        path = self._path(template_id, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(blob, "utf-8")
        return key

    def exists(self, template_id, input_group, inputs, scope: str = "") -> bool:
        return self._path(template_id, self.key(template_id, input_group, inputs, scope)).exists()
