"""Data-source registry — name -> provider, with a configured active source."""

from __future__ import annotations

from ..errors import DataSourceError
from .base import DataSource


class DataSourceRegistry:
    def __init__(self, active: str = "sample"):
        self._sources: dict[str, DataSource] = {}
        self._active = active

    def register(self, source: DataSource) -> None:
        self._sources[source.name] = source

    @property
    def active(self) -> str:
        return self._active

    def get(self, name: str | None = None) -> DataSource:
        key = name or self._active
        if key not in self._sources:
            raise DataSourceError(
                f"Unknown data source '{key}'. Registered: {sorted(self._sources)}"
            )
        return self._sources[key]

    def get_active(self) -> DataSource:
        return self.get(self._active)

    def names(self) -> list[str]:
        return sorted(self._sources)
