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
    "line", "bar", "scatter", "table", "stat", "stat_group", "heatmap", "markdown",
    "fields", "timeseries", "map", "flow", "pie"
]
Severity = Literal["info", "warn", "critical", "low", "medium", "high"]
Width = Literal["full", "half", "third"]
# Color states shared by stat / field boxes: green / orange / red / blue / grey.
ValueState = Literal["good", "warn", "bad", "info", "neutral"]


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
    badge: str | None = None  # highlighted pill under the value (e.g. the root-cause ticket #)
    detail: str | None = None  # prominent (non-muted) secondary line (e.g. the event name)
    sub: str | None = None  # secondary line under the value
    alert: str | None = None  # prominent attention-grabbing alert text (red badge)
    value_text: bool = False  # render the value smaller + one-line (dates/text, not a big number)


class StatGroupData(BaseModel):
    """Several stat cards combined into ONE panel (e.g. the header summary row)."""

    items: list[StatData] = Field(default_factory=list)


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


class MapTicketTag(BaseModel):
    """A ticket shown as a clickable tag on a map site (reuses Step-3 ticket fields)."""

    id: str
    usid: str = ""
    tone: str = "grey"
    type: str = "—"
    type_tone: str = "grey"
    status: str = "—"
    status_tone: str = "grey"
    impact: str = "—"
    impact_tone: str = "grey"
    event: str = "—"
    start: Any = None
    end: Any = None
    prt: Any = None


class MapFeature(BaseModel):
    """One site on the map. ``role`` drives styling/layers; ``color`` is the
    server-resolved marker hex; ``color_state`` is the matching stat/field state."""

    usid: str
    lat: float | None = None  # None => no inventory coordinates (off-map)
    lon: float | None = None
    role: Literal["cluster", "ticket", "neighbor"] = "neighbor"
    trend_status: str | None = None
    trend_start: Any = None
    trend_close: Any = None  # None => ongoing
    color: str = "#9aa3af"
    color_state: ValueState | None = None
    total_calls: int = 0  # calls on this USID within the anomaly window
    calls_known: bool = False  # False => no call-volume data for this USID (vs a real 0)
    tickets: list[MapTicketTag] = Field(default_factory=list)


class MapData(BaseModel):
    """Interactive map panel: sites positioned by lat/lon (offline scatter by
    default; OSM tiles when enabled), color-coded by trend status, with clickable
    ticket tags and layer toggles."""

    features: list[MapFeature] = Field(default_factory=list)
    trend_span: dict[str, Any] | None = None  # the anomaly window {start, end}
    cluster_total_calls: int = 0  # deduped cluster total in the window
    center: dict[str, float] | None = None  # {lat, lon} default view
    radius_km: float = 3.0  # neighbor inclusion radius (for the caption/legend)
    legend: list[dict[str, str]] = Field(default_factory=list)  # [{label, color}]
    missing_coords: int = 0  # sites with no inventory lat/lon
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
    stat_group: StatGroupData | None = None
    fields: FieldsData | None = None
    timeseries: TimeseriesData | None = None
    map: MapData | None = None
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
