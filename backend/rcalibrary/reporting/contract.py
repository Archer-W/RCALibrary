"""Report / panel payload — the JSON contract the frontend renders.

The backend stays renderer-light: for chart panels it emits Plotly-ready
``traces`` + ``layout``; for non-chart panels it emits neutral structures
(``table`` / ``stat`` / ``markdown``). A single unified ``anomalies`` shape is
used across every panel type so the frontend's anomaly summary can aggregate
generically.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PanelType = Literal["line", "bar", "scatter", "table", "stat", "heatmap", "markdown"]
Severity = Literal["info", "warn", "critical", "low", "medium", "high"]
Width = Literal["full", "half", "third"]


class AnomalyPoint(BaseModel):
    x: Any = None
    y: Any = None
    severity: str = "warn"
    reason: str = ""
    label: str | None = None


class AnomalyHighlight(BaseModel):
    points: list[AnomalyPoint] = Field(default_factory=list)
    # Plotly-style shapes (e.g. a dashed threshold line) merged into layout.shapes.
    shapes: list[dict[str, Any]] = Field(default_factory=list)
    severity_counts: dict[str, int] = Field(default_factory=dict)


class TableData(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)


class StatData(BaseModel):
    label: str = ""
    value: Any = None
    unit: str | None = None
    delta: float | None = None
    delta_dir: Literal["up", "down"] | None = None
    state: Literal["good", "bad", "neutral"] | None = None  # colors the value
    sub: str | None = None  # secondary line under the value


class PanelPayload(BaseModel):
    id: str
    type: str
    title: str
    width: Width = "half"
    # Chart panels (line/bar/scatter/heatmap):
    traces: list[dict[str, Any]] = Field(default_factory=list)
    layout: dict[str, Any] = Field(default_factory=dict)
    # Non-chart panels:
    table: TableData | None = None
    stat: StatData | None = None
    markdown: str | None = None
    # Shared:
    anomalies: AnomalyHighlight | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ReportPayload(BaseModel):
    template_id: str
    title: str | None = None
    generated_at: str = ""
    panels: list[PanelPayload] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
