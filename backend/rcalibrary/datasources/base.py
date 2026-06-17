"""Data-source interface + neutral request/result types.

A template's ``data_pull`` is translated by the engine into a source-agnostic
``DataPullRequest``. Whichever ``DataSource`` is active answers it, so swapping
the sample provider for Snowflake requires no template changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import pandas as pd
from pydantic import BaseModel, Field


class NeutralFilter(BaseModel):
    column: str
    op: str  # eq | ne | gt | gte | lt | lte | in | contains
    value: Any


class DataPullRequest(BaseModel):
    """A source-agnostic data request."""

    dataset: str | None = None  # logical dataset name (provider resolves it)
    sql: str | None = None  # optional parameterized SQL (SQL-capable providers only)
    params: dict[str, Any] = Field(default_factory=dict)  # bind params, never concatenated
    filters: list[NeutralFilter] = Field(default_factory=list)
    limit: int | None = None
    columns: list[str] | None = None
    # Columns to force to string (e.g. IDs with leading zeros).
    string_columns: list[str] | None = None
    # Sample-provider convenience: subdir under the samples dir (= template id).
    # Real providers (Snowflake) ignore this.
    namespace: str | None = None


@dataclass
class FetchResult:
    """The result of a fetch — a DataFrame for analysis + JSON helpers."""

    frame: pd.DataFrame

    @property
    def columns(self) -> list[str]:
        return list(self.frame.columns)

    @property
    def row_count(self) -> int:
        return len(self.frame)

    def to_records(self) -> list[dict]:
        return self.frame.to_dict("records")


@runtime_checkable
class DataSource(Protocol):
    name: str

    def fetch(self, request: DataPullRequest) -> FetchResult:  # noqa: D401
        ...

    def health(self) -> dict:  # noqa: D401
        ...
