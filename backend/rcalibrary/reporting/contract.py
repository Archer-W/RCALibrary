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

PanelType = Literal[
    "line", "bar", "scatter", "table", "stat", "heatmap", "markdown", "fields", "timeseries"
]
Severity = Literal["info", "warn", "critical", "low", "medium", "high"]
Width = Literal["full", "half", "third"]
# Color states shared by stat / field boxes: green / orange / red / grey.
ValueState = Literal["good", "warn", "bad", "neutral"]


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
    notice: str | None = None  # shown instead of "No rows." when empty (domain message)


class StatData(BaseModel):
    label: str = ""
    value: Any = None
    unit: str | None = None
    delta: float | None = None
    delta_dir: Literal["up", "down"] | None = None
    state: ValueState | None = None  # colors the value
    sub: str | None = None  # secondary line under the value
    alert: str | None = None  # prominent attention-grabbing alert text (red badge)


class FieldItem(BaseModel):
    """One labeled value box in a ``fields`` panel."""

    label: str = ""
    value: Any = None
    state: ValueState | None = None  # tints the box (e.g. trend status)
    sub: str | None = None  # small caption under the value


class FieldsData(BaseModel):
    """A grid of value boxes — one box per value (Trend ID, USID, status, ...).
    When ``items`` is empty, ``notice`` is shown instead (e.g. a not-found message)."""

    items: list[FieldItem] = Field(default_factory=list)
    notice: str | None = None


class GranularitySpec(BaseModel):
    key: str  # "daily" | "3h" | "hourly"
    label: str


class TimeseriesPoints(BaseModel):
    x: list[Any] = Field(default_factory=list)  # timestamps (ISO strings)
    y: list[Any] = Field(default_factory=list)  # values aligned to x


class TimeseriesSeries(BaseModel):
    usid: str
    label: str
    role: Literal["anchor", "neighbor", "aggregate"] = "neighbor"
    by_gran: dict[str, TimeseriesPoints] = Field(default_factory=dict)  # gran key -> points


class TimeseriesData(BaseModel):
    """Interactive multi-series timeseries: every granularity is embedded so the
    frontend toggles client-side (no re-fetch). One series per USID + an
    aggregate; the frontend shows USID checkboxes and a granularity switcher."""

    default_granularity: str = "daily"
    granularities: list[GranularitySpec] = Field(default_factory=list)
    windows: dict[str, dict[str, Any]] = Field(default_factory=dict)  # gran -> {start,end}
    series: list[TimeseriesSeries] = Field(default_factory=list)
    # Earliest trend start -> latest trend end across the correlated trends;
    # the frontend shades this band behind the lines.
    trend_span: dict[str, Any] | None = None  # {start, end}
    # Optional ticket/event overlays the user can toggle onto the chart (off by
    # default). Each: {id, tone, start, end, lines[]}. Populated via overlay_ref.
    tickets: list[dict[str, Any]] = Field(default_factory=list)
    y_title: str = ""
    notice: str | None = None  # shown when there is nothing to plot


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
    fields: FieldsData | None = None
    timeseries: TimeseriesData | None = None
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
