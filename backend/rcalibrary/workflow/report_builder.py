"""Assemble the frontend ``ReportPayload`` from a template's report layout,
the pulled datasets, and the analysis results.

For chart panels this emits Plotly-ready traces (+ an anomaly markers trace and
threshold shapes); for table/stat/markdown it emits neutral structures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ..analyzers.context import AnalysisResult
from ..datasources.base import FetchResult
from ..reporting.contract import (
    AnomalyHighlight,
    AnomalyPoint,
    FieldItem,
    FieldsData,
    MapData,
    PanelPayload,
    ReportPayload,
    StatData,
    StatGroupData,
    TableData,
    TimeseriesData,
)
from .models import PanelSpec, Template

_ANOMALY_COLOR = "#c0392b"  # NetSkills --bad
_TABLE_ROW_CAP = 500
_DEFAULT_WIDTH = {
    "stat": "third",
    "stat_group": "full",
    "line": "full",
    "scatter": "full",
    "heatmap": "full",
    "table": "full",
    "markdown": "full",
    "fields": "full",
    "timeseries": "full",
    "map": "full",
    "flow": "full",
    "pie": "half",
    "bar": "half",
}


def build(
    template: Template,
    datasets: dict[str, FetchResult],
    analysis_results: dict[str, AnalysisResult],
    warnings: list[str] | None = None,
) -> ReportPayload:
    warnings = warnings or []
    panels = [
        _build_panel(template, spec, datasets, analysis_results)
        for spec in template.report.panels
        if _panel_visible(spec, analysis_results)
    ]

    # Roll up anomalies once per analysis (multiple panels may share an analysis,
    # so summing per-panel would double-count).
    total_anomalies = 0
    severity_totals: dict[str, int] = {}
    for result in analysis_results.values():
        total_anomalies += len(result.anomalies)
        for sev, n in _count_severity(result.anomalies).items():
            severity_totals[sev] = severity_totals.get(sev, 0) + n

    return ReportPayload(
        template_id=template.meta.id,
        title=template.report.title or template.meta.name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        panels=panels,
        summary={"total_anomalies": total_anomalies, "severity_counts": severity_totals},
        warnings=warnings,
    )


def _panel_visible(spec: PanelSpec, analysis_results: dict[str, AnalysisResult]) -> bool:
    """A panel with ``visible_when`` renders only if the referenced analysis
    summary key is truthy (e.g. Step-2 panels gate on Step-1 ``found``)."""
    vw = spec.visible_when
    if not vw:
        return True
    ar = analysis_results.get(vw.ref)
    return bool(ar and ar.summary.get(vw.key))


def _build_panel(
    template: Template,
    spec: PanelSpec,
    datasets: dict[str, FetchResult],
    analysis_results: dict[str, AnalysisResult],
) -> PanelPayload:
    ptype = spec.type.value
    width = spec.width or _DEFAULT_WIDTH.get(ptype, "half")
    panel = PanelPayload(id=spec.id, type=ptype, title=spec.title, width=width, options=spec.options)

    ar = analysis_results.get(spec.analysis_ref) if spec.analysis_ref else None

    if ptype in ("line", "bar", "scatter"):
        _fill_chart(template, spec, datasets, ar, panel)
    elif ptype == "table":
        _fill_table(spec, datasets, ar, panel)
    elif ptype == "stat":
        _fill_stat(spec, ar, panel)
    elif ptype == "stat_group":
        _fill_stat_group(spec, analysis_results, panel)
    elif ptype == "fields":
        _fill_fields(spec, ar, panel)
        # Optional: append/insert extra field boxes computed by another step.
        if spec.overlay_ref and panel.fields is not None:
            _merge_field_overlay(spec, analysis_results, panel)
    elif ptype == "timeseries":
        _fill_timeseries(spec, ar, panel)
        # Optional cross-step overlay (e.g. tickets from Step 3) for this chart.
        if spec.overlay_ref and panel.timeseries is not None:
            overlay_ar = analysis_results.get(spec.overlay_ref)
            if overlay_ar:
                panel.timeseries.tickets = overlay_ar.summary.get("ticket_overlay") or []
    elif ptype == "map":
        _fill_map(spec, ar, panel)
    elif ptype == "pie":
        _fill_pie(spec, datasets, ar, panel)
    elif ptype == "heatmap":
        _fill_heatmap(spec, datasets, panel)
    elif ptype == "markdown":
        # Text can come from an analysis result (analysis_ref + encoding.value)
        # or fall back to a static options.text.
        text = ar.summary.get(spec.encoding.value) if (ar and spec.encoding.value) else None
        panel.markdown = text if text is not None else str(spec.options.get("text", spec.title))
    return panel


# -- chart panels -----------------------------------------------------------
def _fill_chart(template, spec, datasets, ar, panel) -> None:
    enc = spec.encoding
    frame = _frame_for(spec.dataset, datasets)
    traces: list[dict[str, Any]] = []

    if frame is not None and enc.x and enc.y and enc.y in frame.columns:
        if enc.series and enc.series in frame.columns:
            for key, grp in frame.groupby(enc.series):
                traces.append(_series_trace(spec, str(key), grp[enc.x].tolist(), grp[enc.y].tolist()))
        else:
            traces.append(_series_trace(spec, spec.title, frame[enc.x].tolist(), frame[enc.y].tolist()))

    layout: dict[str, Any] = {
        "xaxis": {"title": spec.options.get("x_title", enc.x or "")},
        "yaxis": {"title": spec.options.get("y_title", enc.y or "")},
    }

    anomalies = _resolve_anomalies(template, spec, datasets, ar)
    if anomalies and anomalies.points:
        traces.append(
            {
                "type": "scatter",
                "mode": "markers",
                "name": "Anomalies",
                "x": [p.x for p in anomalies.points],
                "y": [p.y for p in anomalies.points],
                "marker": {"color": _ANOMALY_COLOR, "size": 9, "symbol": "x"},
                "hovertext": [p.reason for p in anomalies.points],
                "hoverinfo": "text+x+y",
            }
        )
    if anomalies and anomalies.shapes:
        layout["shapes"] = anomalies.shapes

    panel.traces = traces
    panel.layout = layout
    panel.anomalies = anomalies


def _series_trace(spec, name, x, y) -> dict[str, Any]:
    if spec.type.value == "bar":
        return {"type": "bar", "name": name, "x": x, "y": y}
    mode = "markers" if spec.type.value == "scatter" else "lines"
    return {"type": "scatter", "mode": mode, "name": name, "x": x, "y": y}


def _fill_pie(spec, datasets, ar, panel) -> None:
    """Pie/donut from an analysis `table` (preferred) or the panel's dataset, using
    encoding.labels/values (falling back to x/y). Emits a Plotly pie trace."""
    enc = spec.encoding
    records: list[dict] = ar.table if (ar and ar.table) else []
    if not records:
        frame = _frame_for(spec.dataset, datasets)
        records = frame.to_dict("records") if frame is not None else []
    lab, val = (enc.labels or enc.x), (enc.values or enc.y)
    labels = [_py(r.get(lab)) for r in records] if lab else []
    values = [_py(r.get(val)) for r in records] if val else []
    if not labels or not values:
        # no data (e.g. trend not found) -> a readable message, not an empty pie
        notice = (ar.summary.get("empty_notice") if ar else None) or "No data to chart."
        panel.markdown = notice
        panel.type = "markdown"
        return
    panel.traces = [{
        "type": "pie", "labels": labels, "values": values,
        "textinfo": "label+percent", "hole": spec.options.get("hole", 0),
    }]
    panel.layout = {"showlegend": True}


# -- non-chart panels -------------------------------------------------------
def _fill_table(spec, datasets, ar, panel) -> None:
    records: list[dict] = []
    if ar and ar.table:
        records = ar.table
    else:
        frame = _frame_for(spec.dataset, datasets)
        if frame is not None:
            records = frame.to_dict("records")

    columns = spec.encoding.columns or (list(records[0].keys()) if records else [])
    rows = [[_py(rec.get(c)) for c in columns] for rec in records[:_TABLE_ROW_CAP]]
    # On an empty table, an analyzer may supply a domain message via
    # summary["empty_notice"] (shown instead of the generic "No rows.").
    notice = ar.summary.get("empty_notice") if (ar and not rows) else None
    panel.table = TableData(columns=columns, rows=rows, notice=notice)
    # Surface anomaly counts so the table panel can show a severity chip too.
    if ar and ar.anomalies:
        panel.anomalies = AnomalyHighlight(severity_counts=_count_severity(ar.anomalies))


def _fill_stat(spec, ar, panel) -> None:
    summary = ar.summary if ar else {}
    enc = spec.encoding
    panel.stat = StatData(
        label=spec.title,
        value=_py(summary.get(enc.value)) if enc.value else None,
        unit=spec.options.get("unit"),
        state=summary.get(enc.state) if enc.state else None,
        badge=summary.get(enc.badge) if enc.badge else None,
        detail=summary.get(enc.detail) if enc.detail else None,
        sub=summary.get(enc.sub) if enc.sub else None,
        alert=summary.get(enc.alert) if enc.alert else None,
    )
    if ar and ar.anomalies:
        panel.anomalies = AnomalyHighlight(severity_counts=_count_severity(ar.anomalies))


def _fill_stat_group(spec, analysis_results, panel) -> None:
    """Combine several stat cards into ONE panel. Each entry in ``options.stats`` is
    a mini stat-spec: ``{title, analysis_ref, value, state, sub, badge, detail,
    alert, unit, value_text, visible_when:{ref,key}}`` — read from the referenced
    analysis result. A gated entry whose ``visible_when`` is falsy is dropped."""
    items: list[StatData] = []
    for sub in spec.options.get("stats", []):
        vw = sub.get("visible_when")
        if vw:
            gate = analysis_results.get(vw.get("ref"))
            if not (gate and gate.summary.get(vw.get("key"))):
                continue
        ar = analysis_results.get(sub.get("analysis_ref"))
        summary = ar.summary if ar else {}
        get = lambda k: (summary.get(sub[k]) if sub.get(k) else None)  # noqa: E731
        items.append(StatData(
            label=sub.get("title", ""),
            value=_py(get("value")),
            unit=sub.get("unit"),
            state=get("state"),
            badge=get("badge"),
            detail=get("detail"),
            sub=get("sub"),
            alert=get("alert"),
            value_text=bool(sub.get("value_text")),
        ))
    panel.stat_group = StatGroupData(items=items)


def _fill_fields(spec, ar, panel) -> None:
    # The analysis supplies a ready-made structure under encoding.value:
    #   {"items": [{"label","value","state","sub"}, ...], "notice": "..."}
    # (a bare list is also accepted). On not-found, items is empty + notice set.
    summary = ar.summary if ar else {}
    raw = summary.get(spec.encoding.value) if spec.encoding.value else None
    if isinstance(raw, dict):
        panel.fields = FieldsData(**raw)
    elif isinstance(raw, list):
        panel.fields = FieldsData(items=raw)
    else:
        panel.fields = FieldsData()


def _fill_timeseries(spec, ar, panel) -> None:
    # The analysis supplies the whole structure (all granularities embedded so
    # the frontend toggles client-side) under encoding.value -> TimeseriesData.
    summary = ar.summary if ar else {}
    raw = summary.get(spec.encoding.value) if spec.encoding.value else None
    panel.timeseries = TimeseriesData(**raw) if isinstance(raw, dict) else TimeseriesData()


def _fill_map(spec, ar, panel) -> None:
    # The analysis supplies the whole structure under encoding.value -> MapData.
    summary = ar.summary if ar else {}
    raw = summary.get(spec.encoding.value) if spec.encoding.value else None
    panel.map = MapData(**raw) if isinstance(raw, dict) else MapData()


def _merge_field_overlay(spec, analysis_results, panel) -> None:
    """Insert extra field boxes published by another analysis as
    ``summary["field_overlay"] = {after_label?, items:[{label,value,state?,sub?}]}``.
    Inserted right after the box whose label == after_label, else appended."""
    ov = analysis_results.get(spec.overlay_ref)
    data = (ov.summary.get("field_overlay") if ov else None) or {}
    raw_items = data.get("items") or []
    if not raw_items:
        return
    extra = [FieldItem(**it) if isinstance(it, dict) else it for it in raw_items]
    items = panel.fields.items
    after = data.get("after_label")
    idx = next((i for i, b in enumerate(items) if b.label == after), None) if after else None
    if idx is None:
        panel.fields.items = items + extra
    else:
        panel.fields.items = items[: idx + 1] + extra + items[idx + 1 :]


def _fill_heatmap(spec, datasets, panel) -> None:
    enc = spec.encoding
    frame = _frame_for(spec.dataset, datasets)
    if frame is None or not (enc.x and enc.y and enc.value):
        panel.markdown = "Heatmap requires encoding.x, encoding.y and encoding.value."
        panel.type = "markdown"
        return
    try:
        pivot = frame.pivot_table(index=enc.y, columns=enc.x, values=enc.value, aggfunc="mean")
        panel.traces = [
            {
                "type": "heatmap",
                "x": [str(c) for c in pivot.columns.tolist()],
                "y": [str(i) for i in pivot.index.tolist()],
                "z": pivot.values.tolist(),
            }
        ]
        panel.layout = {
            "xaxis": {"title": spec.options.get("x_title", enc.x)},
            "yaxis": {"title": spec.options.get("y_title", enc.y)},
        }
    except Exception as exc:  # noqa: BLE001
        panel.markdown = f"Could not build heatmap: {exc}"
        panel.type = "markdown"


# -- anomaly resolution -----------------------------------------------------
def _resolve_anomalies(template, spec, datasets, ar) -> AnomalyHighlight | None:
    if ar is None:
        return None
    enc = spec.encoding
    # Resolve the x-coordinate for each anomaly from the analysis's own dataset.
    step = template.analysis_by_id(spec.analysis_ref) if spec.analysis_ref else None
    src_frame = _frame_for(step.inputs.get("dataset") if step else None, datasets)

    points: list[AnomalyPoint] = []
    for a in ar.anomalies:
        idx = a.get("index")
        x_val = None
        if src_frame is not None and enc.x and enc.x in src_frame.columns and idx in src_frame.index:
            x_val = _py(src_frame.loc[idx, enc.x])
        elif idx is not None:
            x_val = idx
        points.append(
            AnomalyPoint(
                x=x_val,
                y=_py(a.get("value")),
                severity=a.get("severity", "warn"),
                reason=a.get("reason", ""),
            )
        )

    shapes = [_annotation_to_shape(an) for an in ar.annotations if an.get("type") == "hline"]
    return AnomalyHighlight(
        points=points,
        shapes=[s for s in shapes if s],
        severity_counts=_count_severity(ar.anomalies),
    )


def _annotation_to_shape(annotation: dict) -> dict | None:
    if annotation.get("type") != "hline" or "y" not in annotation:
        return None
    return {
        "type": "line",
        "xref": "paper",
        "x0": 0,
        "x1": 1,
        "yref": "y",
        "y0": annotation["y"],
        "y1": annotation["y"],
        "line": {"color": _ANOMALY_COLOR, "width": 1.5, "dash": "dash"},
    }


# -- helpers ----------------------------------------------------------------
def _frame_for(dataset_id: str | None, datasets: dict[str, FetchResult]) -> pd.DataFrame | None:
    if not dataset_id or dataset_id not in datasets:
        return None
    return datasets[dataset_id].frame


def _count_severity(anomalies: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in anomalies:
        sev = a.get("severity", "warn")
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def _py(value: Any) -> Any:
    """Convert numpy/pandas scalars to plain Python for JSON serialization."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return value.item()
        except Exception:  # noqa: BLE001
            return value
    return value
