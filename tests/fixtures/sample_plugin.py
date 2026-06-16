"""A sample use-case plugin used to test the extension loader.

It demonstrates the three registration mechanisms a real use-case plugin uses.
"""

from rcalibrary import extensions
from rcalibrary.analyzers import analyzer
from rcalibrary.analyzers.context import AnalysisResult
from rcalibrary.auth.base import Principal
from rcalibrary.datasources.base import DataSource, FetchResult


@analyzer("sample_plugin_analyzer")
def _sample_analyzer(ctx):
    return AnalysisResult(summary={"rows": int(len(ctx.dataset))})


class _PluginDataSource(DataSource):
    name = "plugin_ds"

    def fetch(self, request) -> FetchResult:  # pragma: no cover - not exercised
        raise NotImplementedError

    def health(self) -> dict:
        return {"name": self.name, "ready": False}


class _PluginAuthProvider:
    def authenticate(self, request=None) -> Principal:
        return Principal(subject="plugin-user", roles=["admin"], is_authenticated=True)


extensions.register_datasource(_PluginDataSource())
extensions.set_auth_provider(_PluginAuthProvider())
