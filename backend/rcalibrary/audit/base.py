"""Audit interfaces. The engine emits one ``AuditEvent`` per template run."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    event_type: str = "template_run"
    principal_subject: str = "guest"
    template_id: str | None = None
    level: int | None = None
    status: str = "ok"
    duration_ms: float | None = None
    anomaly_count: int | None = None
    timestamp: str = ""
    # Input *keys* are recorded by default, not values (avoid logging PII/secrets).
    extra: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class AuditLogger(Protocol):
    def emit(self, event: AuditEvent) -> None:  # noqa: D401
        ...
