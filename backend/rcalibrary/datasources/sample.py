"""Sample data provider — serves CSV files from ``data/samples/``.

Resolution order for a request with ``dataset=foo`` and ``namespace=tmpl``:
  1. ``<samples_dir>/tmpl/foo.csv``  (per-template sample data)
  2. ``<samples_dir>/foo.csv``       (shared sample data)

Filters are applied generically. A couple of documented param conventions make
the demo feel real:
  * a param whose key matches a column → equality filter
  * ``lookback_hours`` + a parseable ``ts`` column → keep the trailing window
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..errors import DataSourceError
from .base import DataPullRequest, DataSource, FetchResult, NeutralFilter

name = "sample"

_OPS = {
    "eq": lambda s, v: s == v,
    "ne": lambda s, v: s != v,
    "gt": lambda s, v: s > v,
    "gte": lambda s, v: s >= v,
    "lt": lambda s, v: s < v,
    "lte": lambda s, v: s <= v,
    "in": lambda s, v: s.isin(v if isinstance(v, (list, tuple, set)) else [v]),
    "contains": lambda s, v: s.astype(str).str.contains(str(v), case=False, na=False),
}


class SampleDataProvider(DataSource):
    name = "sample"

    def __init__(self, samples_dir: Path):
        self.samples_dir = Path(samples_dir)

    # -- DataSource interface ------------------------------------------------
    def health(self) -> dict:
        return {"name": self.name, "ready": self.samples_dir.exists(), "dir": str(self.samples_dir)}

    def fetch(self, request: DataPullRequest) -> FetchResult:
        if not request.dataset:
            raise DataSourceError("SampleDataProvider requires a 'dataset' name (got SQL or empty).")
        path = self._resolve_path(request.dataset, request.namespace)
        try:
            frame = pd.read_csv(path)
        except Exception as exc:  # noqa: BLE001
            raise DataSourceError(f"Failed to read sample dataset '{request.dataset}': {exc}") from exc

        frame = self._apply_filters(frame, request.filters)
        frame = self._apply_params(frame, request.params)
        if request.columns:
            keep = [c for c in request.columns if c in frame.columns]
            if keep:
                frame = frame[keep]
        if request.limit is not None:
            frame = frame.head(request.limit)
        return FetchResult(frame=frame.reset_index(drop=True))

    # -- helpers -------------------------------------------------------------
    def _resolve_path(self, dataset: str, namespace: str | None) -> Path:
        candidates = []
        if namespace:
            candidates.append(self.samples_dir / namespace / f"{dataset}.csv")
        candidates.append(self.samples_dir / f"{dataset}.csv")
        for path in candidates:
            if path.exists():
                return path
        raise DataSourceError(
            f"Sample dataset '{dataset}' not found (looked in: "
            + ", ".join(str(c) for c in candidates)
            + ")"
        )

    def _apply_filters(self, frame: pd.DataFrame, filters: list[NeutralFilter]) -> pd.DataFrame:
        for flt in filters:
            if flt.column not in frame.columns:
                continue
            op = _OPS.get(flt.op)
            if op is None:
                raise DataSourceError(f"Unsupported filter op '{flt.op}'")
            try:
                frame = frame[op(frame[flt.column], flt.value)]
            except Exception as exc:  # noqa: BLE001
                raise DataSourceError(f"Filter on '{flt.column}' failed: {exc}") from exc
        return frame

    def _apply_params(self, frame: pd.DataFrame, params: dict) -> pd.DataFrame:
        for key, value in params.items():
            if key == "lookback_hours":
                frame = self._apply_lookback(frame, value)
            elif key in frame.columns:
                frame = frame[frame[key] == value]
        return frame

    @staticmethod
    def _apply_lookback(frame: pd.DataFrame, hours) -> pd.DataFrame:
        if "ts" not in frame.columns or hours is None:
            return frame
        try:
            ts = pd.to_datetime(frame["ts"], errors="coerce")
            if ts.isna().all():
                return frame
            cutoff = ts.max() - pd.Timedelta(hours=float(hours))
            return frame[ts >= cutoff]
        except Exception:  # noqa: BLE001 - lookback is best-effort
            return frame
