"""Public extension API for use-case plugins.

This is the seam that lets a **use-case repo extend the framework WITHOUT editing
any framework file**. A use-case repo:

  1. writes plugin modules (in its own package), then
  2. lists them in the ``RCA_PLUGINS`` env var (comma-separated import paths).

At startup the framework imports each plugin module; the module's import-time
side effects register everything:

  * **Analyzers** — decorate with ``@analyzer("name")`` (from
    ``rcalibrary.analyzers``); it registers on the shared default registry.
  * **Data sources** — call ``extensions.register_datasource(provider)`` and set
    ``RCA_DATASOURCE`` to the provider's ``name``.
  * **Authentication** — call ``extensions.set_auth_provider(provider)``.

Framework code never imports use-case modules directly; it only discovers them
through this API + config. See docs/07-building-use-cases.md.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable

from .auth.base import AuthProvider, Principal
from .datasources.base import DataSource

_datasources: list[DataSource] = []
_auth_provider: AuthProvider | None = None
# provider name -> factory(template_engine) -> AIPanelEngine. The other agent
# registers its real LLM engine here (e.g. for RCA_AI_PROVIDER=anthropic) without
# editing framework files. See docs/11-ai-panel-builder.md.
_ai_engine_factories: dict[str, Callable[[Any], Any]] = {}


# -- data sources -----------------------------------------------------------
def register_datasource(provider: DataSource) -> None:
    """Register an additional data source (e.g. a real Snowflake provider)."""
    _datasources.append(provider)


def registered_datasources() -> list[DataSource]:
    return list(_datasources)


# -- authentication ---------------------------------------------------------
def set_auth_provider(provider: AuthProvider) -> None:
    """Install the auth provider used by the API (replaces anonymous)."""
    global _auth_provider
    _auth_provider = provider


def get_auth_provider() -> AuthProvider | None:
    return _auth_provider


# -- AI panel engine --------------------------------------------------------
def register_ai_engine(provider: str, factory: Callable[[Any], Any]) -> None:
    """Register an AI panel engine factory for an ``RCA_AI_PROVIDER`` value.

    ``factory(template_engine) -> AIPanelEngine``. The other agent uses this to plug
    in a real LLM engine (e.g. a LangGraph + Claude MCP client) without editing
    framework files; select it with ``RCA_AI_PROVIDER=<provider>``."""
    _ai_engine_factories[provider] = factory


def get_ai_engine_factory(provider: str) -> Callable[[Any], Any] | None:
    return _ai_engine_factories.get(provider)


# -- plugin loading ---------------------------------------------------------
def load_plugins(module_paths: list[str]) -> list[str]:
    """Import each plugin module so its registrations take effect.

    Returns the list of successfully imported module paths.
    """
    loaded: list[str] = []
    for raw in module_paths:
        path = raw.strip()
        if not path:
            continue
        importlib.import_module(path)
        loaded.append(path)
    return loaded


# -- testing helper ---------------------------------------------------------
def _reset() -> None:
    """Clear registered extensions (used by tests for isolation)."""
    global _auth_provider
    _datasources.clear()
    _auth_provider = None
    _ai_engine_factories.clear()


__all__ = [
    "AuthProvider",
    "DataSource",
    "Principal",
    "register_datasource",
    "registered_datasources",
    "set_auth_provider",
    "get_auth_provider",
    "register_ai_engine",
    "get_ai_engine_factory",
    "load_plugins",
]
