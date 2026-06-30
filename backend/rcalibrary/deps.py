"""Dependency providers (singletons). FastAPI routes ``Depends`` on these.

Each is ``lru_cache``-d so the registries/providers are built once. Swapping a
provider later (real auth, Snowflake, a DB audit sink) means changing only the
factory here — route signatures are untouched.
"""

from __future__ import annotations

from functools import lru_cache

from . import extensions
from .ai.engine import AIPanelEngine, DisabledAIEngine, LLMToolEngine, SimulatedAIEngine

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
from .persistence.report_cache import ReportCache
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
    # Data sources contributed by use-case plugins (e.g. a real Snowflake/DB provider).
    for provider in extensions.registered_datasources():
        registry.register(provider)
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
def get_report_cache() -> ReportCache:
    settings = get_settings()
    return ReportCache(settings.report_cache_dir, max_bytes=settings.report_cache_max_bytes)


@lru_cache
def get_ai_panel_engine() -> AIPanelEngine:
    """The AI engine behind /panel/ai, selected by ``RCA_AI_PROVIDER``.

    ``simulated`` (default) = the free/offline deterministic engine shipped here.
    A use-case/LLM plugin registers a real engine via
    ``extensions.register_ai_engine(provider, factory)`` and selects it with the
    provider name; an unknown/unregistered provider degrades to disabled (never
    500s). See docs/11-ai-panel-builder.md."""
    settings = get_settings()
    if not settings.ai_enabled:
        return DisabledAIEngine()
    if settings.ai_provider == "simulated":
        return SimulatedAIEngine(
            get_engine(), ttl_s=settings.ai_session_ttl_s, max_turns=settings.ai_max_turns
        )
    # Real LLM over an OpenAI-compatible endpoint (e.g. a local gpt-oss). The `openai`
    # package is imported lazily inside the client; a missing base_url -> disabled (so a
    # half-configured deployment degrades gracefully instead of erroring on first use).
    if settings.ai_provider in ("openai", "local", "gpt-oss", "gpt_oss"):
        if not settings.ai_base_url:
            return DisabledAIEngine()
        from .ai.llm import OpenAICompatLLMClient

        client = OpenAICompatLLMClient(
            base_url=settings.ai_base_url,
            model=settings.ai_model,
            api_key=settings.ai_api_key,
            timeout=settings.ai_request_timeout,
            temperature=settings.ai_temperature,
            tool_choice=settings.ai_tool_choice,
        )
        return LLMToolEngine(
            get_engine(), client, ttl_s=settings.ai_session_ttl_s, max_turns=settings.ai_max_turns
        )
    # A use-case/LLM plugin may register its own engine for a custom provider name.
    factory = extensions.get_ai_engine_factory(settings.ai_provider)
    if factory is not None:
        return factory(get_engine())
    return DisabledAIEngine()


@lru_cache
def get_solution_registry() -> SolutionRegistry:
    registry = SolutionRegistry()
    registry.register(FixedWorkflowSolution(get_template_registry(), get_engine()))
    registry.register(LangGraphSolution())
    registry.register(CliAgentSolution())
    return registry


def get_principal() -> Principal:
    # A use-case plugin may install a real auth provider; otherwise anonymous.
    provider = extensions.get_auth_provider() or _auth_provider
    return provider.authenticate()
