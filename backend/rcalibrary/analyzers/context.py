"""Inputs/outputs for analyzer functions.

An analyzer is a pure function ``(AnalysisContext) -> AnalysisResult``. It reads
the dataset + params and returns structured anomalies; it must not mutate inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class AnalysisContext:
    dataset: pd.DataFrame
    params: dict[str, Any]
    inputs: dict[str, Any]  # validated template inputs (read-only)
    # Results of analysis steps that ran earlier in this run, keyed by step id.
    # Lets a step chain on an earlier one (e.g. Step 2 reads Step 1's anchor).
    results: dict[str, "AnalysisResult"] = field(default_factory=dict)
    # Every pulled dataset by data_pull id (``dataset`` is the step's primary).
    # Lets a step read more than one source (e.g. neighbors + call volume).
    datasets: dict[str, pd.DataFrame] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    # Scalar metrics, e.g. {"breach_count": 7}. Used by `stat` panels.
    summary: dict[str, Any] = field(default_factory=dict)
    # Each anomaly: {"index", "column", "value", "severity", "reason", ...}.
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    # Plot overlays, e.g. {"type": "hline", "y": 120, "label": "threshold"}.
    annotations: list[dict[str, Any]] = field(default_factory=list)
    # Optional row subset for `table` panels (list of record dicts).
    table: list[dict[str, Any]] = field(default_factory=list)
