"""Example real data source. Flesh out fetch() and set RCA_DATASOURCE=snowflake.

Copy the framework's stub at framework/backend/rcalibrary/datasources/snowflake.py
for the intended dataset/sql/filters -> parameterized-query mapping. Do NOT edit
the framework file in place (it's framework-owned and would be lost on submodule
update).
"""

from __future__ import annotations

from rcalibrary.datasources.base import DataPullRequest, DataSource, FetchResult


class SnowflakeProvider(DataSource):
    name = "snowflake"

    def __init__(self, **cfg):
        self.cfg = cfg

    def health(self) -> dict:
        return {"name": self.name, "ready": bool(self.cfg.get("account"))}

    def fetch(self, request: DataPullRequest) -> FetchResult:
        # import snowflake.connector
        # conn = snowflake.connector.connect(**self.cfg)
        # sql, binds = self._compile(request)   # dataset/filters -> parameterized SQL
        # cur = conn.cursor(); cur.execute(sql, binds)
        # return FetchResult(frame=cur.fetch_pandas_all())
        raise NotImplementedError("Implement SnowflakeProvider.fetch for your schema.")
