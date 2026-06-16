"""No-op audit logger (the default). Records nothing."""

from __future__ import annotations

from .base import AuditEvent


class NoopAuditLogger:
    def emit(self, event: AuditEvent) -> None:  # noqa: D401
        return None
