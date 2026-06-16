"""File audit logger — appends one JSON object per line. Opt in with
``RCA_AUDIT_MODE=file``. PHASE-2: swap for a database / telemetry sink."""

from __future__ import annotations

from pathlib import Path

from .base import AuditEvent


class FileAuditLogger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def emit(self, event: AuditEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(event.model_dump_json() + "\n")
