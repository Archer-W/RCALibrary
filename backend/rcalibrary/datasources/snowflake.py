"""Snowflake data provider — PHASE-2 STUB.

This documents the intended implementation so the real provider drops in behind
the same ``DataSource`` interface with no template/engine/UI changes. To enable
later: implement ``fetch`` with ``snowflake-connector-python``, set
``RCA_DATASOURCE=snowflake`` and populate the ``SNOWFLAKE_*`` env vars.
"""

from __future__ import annotations

from ..errors import DataSourceError
from .base import DataPullRequest, DataSource, FetchResult

name = "snowflake"


class SnowflakeProvider(DataSource):
    name = "snowflake"

    def __init__(
        self,
        account: str | None = None,
        user: str | None = None,
        password: str | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
        role: str | None = None,
    ):
        self.account = account
        self.user = user
        self.password = password
        self.warehouse = warehouse
        self.database = database
        self.schema = schema
        self.role = role

    def health(self) -> dict:
        return {"name": self.name, "ready": False, "status": "stub"}

    def fetch(self, request: DataPullRequest) -> FetchResult:
        """PHASE-2: planned implementation.

        - ``request.dataset`` -> a fully-qualified view/table; or run
          ``request.sql`` with named bind params from ``request.params``
          (``%(name)s`` paramstyle) — never string-concatenated.
        - ``request.filters`` -> compiled to a parameterized WHERE clause.
        - result via ``cursor.fetch_pandas_all()`` -> DataFrame -> FetchResult.
        """
        raise DataSourceError(
            "SnowflakeProvider is a Phase-2 stub. Set RCA_DATASOURCE=sample to use "
            "the bundled sample data, or implement SnowflakeProvider.fetch()."
        )
