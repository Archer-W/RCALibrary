"""Built-in analyzers. Importing this module registers them on ``default_registry``."""

from __future__ import annotations

import pandas as pd

from ..errors import AnalysisError
from .context import AnalysisContext, AnalysisResult
from .registry import analyzer

_COMPARATORS = {
    "gt": lambda s, t: s > t,
    "gte": lambda s, t: s >= t,
    "lt": lambda s, t: s < t,
    "lte": lambda s, t: s <= t,
    "eq": lambda s, t: s == t,
    "ne": lambda s, t: s != t,
}


def _require_column(ctx: AnalysisContext, col: str) -> pd.Series:
    if col not in ctx.dataset.columns:
        raise AnalysisError(f"column '{col}' not in dataset (have: {list(ctx.dataset.columns)})")
    return ctx.dataset[col]


@analyzer("threshold_breach")
def threshold_breach(ctx: AnalysisContext) -> AnalysisResult:
    """Flag rows where ``column <op> threshold``. Declarative, no stats."""
    col = ctx.params.get("column")
    if not col:
        raise AnalysisError("threshold_breach requires params.column")
    op = ctx.params.get("op", "gt")
    if op not in _COMPARATORS:
        raise AnalysisError(f"threshold_breach: unsupported op '{op}'")
    try:
        threshold = float(ctx.params["threshold"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AnalysisError("threshold_breach requires a numeric params.threshold") from exc
    severity = ctx.params.get("severity", "medium")

    series = pd.to_numeric(_require_column(ctx, col), errors="coerce")
    mask = _COMPARATORS[op](series, threshold).fillna(False)
    breaches = ctx.dataset[mask]

    anomalies = [
        {
            "index": int(idx),
            "column": col,
            "value": float(val),
            "severity": severity,
            "reason": f"{col} {op} {threshold}",
        }
        for idx, val in series[mask].items()
    ]
    return AnalysisResult(
        summary={"breach_count": int(mask.sum()), "threshold": threshold, "column": col},
        anomalies=anomalies,
        annotations=[{"type": "hline", "y": threshold, "label": f"threshold ({threshold})"}],
        table=breaches.to_dict("records"),
    )


@analyzer("zscore_anomaly")
def zscore_anomaly(ctx: AnalysisContext) -> AnalysisResult:
    """Flag rows whose value is ``>= z_threshold`` standard deviations from the mean."""
    col = ctx.params.get("column")
    if not col:
        raise AnalysisError("zscore_anomaly requires params.column")
    z_threshold = float(ctx.params.get("z_threshold", 3.0))

    series = pd.to_numeric(_require_column(ctx, col), errors="coerce")
    mean = float(series.mean())
    std = float(series.std(ddof=0)) or 1.0
    zscores = (series - mean) / std
    mask = (zscores.abs() >= z_threshold).fillna(False)

    anomalies = [
        {
            "index": int(idx),
            "column": col,
            "value": float(series[idx]),
            "zscore": round(float(zscores[idx]), 3),
            "severity": "high" if abs(zscores[idx]) >= z_threshold * 1.5 else "medium",
            "reason": f"|z|={abs(zscores[idx]):.2f} >= {z_threshold}",
        }
        for idx in series.index[mask]
    ]
    return AnalysisResult(
        summary={
            "anomaly_count": int(mask.sum()),
            "mean": round(mean, 4),
            "std": round(std, 4),
            "column": col,
        },
        anomalies=anomalies,
        table=ctx.dataset[mask].to_dict("records"),
    )


@analyzer("passthrough")
def passthrough(ctx: AnalysisContext) -> AnalysisResult:
    """No analysis — used by panels that just render a dataset."""
    return AnalysisResult(summary={"row_count": int(len(ctx.dataset))})
