import pathlib
import sys

import pytest

from rcalibrary import extensions
from rcalibrary.analyzers import default_registry

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def clean_extensions():
    yield
    extensions._reset()
    default_registry._fns.pop("sample_plugin_analyzer", None)


def test_load_plugins_registers_analyzer_datasource_and_auth(clean_extensions):
    if str(FIXTURES) not in sys.path:
        sys.path.insert(0, str(FIXTURES))

    loaded = extensions.load_plugins(["sample_plugin"])
    assert loaded == ["sample_plugin"]

    # Analyzer registered on the shared registry (engine + loader use this one).
    assert default_registry.has("sample_plugin_analyzer")

    # Data source registered via the extension API.
    assert any(d.name == "plugin_ds" for d in extensions.registered_datasources())

    # Auth provider installed and used.
    provider = extensions.get_auth_provider()
    assert provider is not None
    principal = provider.authenticate()
    assert principal.subject == "plugin-user"
    assert principal.is_authenticated is True


def test_load_plugins_ignores_blank_entries(clean_extensions):
    assert extensions.load_plugins(["", "  "]) == []
