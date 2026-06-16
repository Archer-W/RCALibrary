from rcalibrary.analyzers import default_registry
from rcalibrary.config import REPO_ROOT
from rcalibrary.workflow.loader import TemplateLoader
from rcalibrary.workflow.registry import TemplateRegistry

DEMO = REPO_ROOT / "templates" / "ana.rca.generic-demo" / "template.yaml"


def test_loads_demo_template():
    loader = TemplateLoader(default_registry)
    template = loader.load_file(DEMO)
    assert template.meta.id == "ana.rca.generic-demo"
    assert [i.name for i in template.inputs] == ["node_id", "lookback_hours", "latency_slo_ms"]
    assert {p.id for p in template.data_pulls} == {"latency_ts", "error_counts"}


def test_registry_discovers_demo():
    loader = TemplateLoader(default_registry)
    registry = TemplateRegistry(REPO_ROOT / "templates", loader).discover()
    assert "ana.rca.generic-demo" in registry.ids()
    # discovery is deterministic / sorted
    assert registry.ids() == sorted(registry.ids())
