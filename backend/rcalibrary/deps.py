"""Dependency providers (singletons). FastAPI routes ``Depends`` on these.

Each is ``lru_cache``-d so the registries/providers are built once. Swapping a
provider later (real auth, Snowflake, a DB audit sink) means changing only the
factory here — route signatures are untouched.
"""

from __future__ import annotations

from functools import lru_cache

# Importing the package registers the built-in analyzers via its __init__.
from .analyzers import default_registry as analyzer_registry
from .audit.file import FileAuditLogger
from .audit.noop import NoopAuditLogger
from .auth.anonymous import AnonymousAuthProvider
from .auth.base import Principal
from .config import get_settings
from .datasources.registry import DataSourceRegistry
from .datasources.sample import SampleDataProvider
from .datasources.snowflake import SnowflakeProvider
from .solutions.cli_agent import CliAgentSolution
from .solutions.fixed_workflow import FixedWorkflowSolution
from .solutions.langgraph_flow import LangGraphSolution
from .solutions.registry import SolutionRegistry
from .workflow.engine import TemplateEngine
from .workflow.loader import TemplateLoader
from .workflow.registry import TemplateRegistry

_auth_provider = AnonymousAuthProvider()


@lru_cache
def get_datasource_registry() -> DataSourceRegistry:
    settings = get_settings()
    registry = DataSourceRegistry(active=settings.datasource)
    registry.register(SampleDataProvider(settings.samples_dir))
    registry.register(SnowflakeProvider())  # Phase-2 stub
    return registry


@lru_cache
def get_audit_logger():
    settings = get_settings()
    if settings.audit_mode == "file":
        return FileAuditLogger(settings.audit_file)
    return NoopAuditLogger()


@lru_cache
def get_template_registry() -> TemplateRegistry:
    settings = get_settings()
    loader = TemplateLoader(analyzer_registry)
    return TemplateRegistry(settings.templates_dir, loader).discover()


@lru_cache
def get_engine() -> TemplateEngine:
    return TemplateEngine(get_datasource_registry(), analyzer_registry, get_audit_logger())


@lru_cache
def get_solution_registry() -> SolutionRegistry:
    registry = SolutionRegistry()
    registry.register(FixedWorkflowSolution(get_template_registry(), get_engine()))
    registry.register(LangGraphSolution())
    registry.register(CliAgentSolution())
    return registry


def get_principal() -> Principal:
    return _auth_provider.authenticate()
