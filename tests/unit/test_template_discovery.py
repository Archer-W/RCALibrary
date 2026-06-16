from rcalibrary.analyzers import default_registry
from rcalibrary.workflow.loader import TemplateLoader
from rcalibrary.workflow.registry import TemplateRegistry

VALID = """
meta: { id: test.ok, name: OK }
data_pulls:
  - { id: d1, query: { dataset: ds1 } }
analysis:
  - { id: a1, analyzer: passthrough, inputs: { dataset: d1 } }
report: { panels: [ { id: p1, type: table, title: T, dataset: d1, analysis_ref: a1 } ] }
"""

INVALID = """
meta: { id: test.broken, name: Broken }
data_pulls:
  - { id: d1, query: { dataset: ds1 } }
analysis:
  - { id: a1, analyzer: this_analyzer_does_not_exist, inputs: { dataset: d1 } }
report: { panels: [] }
"""


def _write(tmp_path, folder, body):
    d = tmp_path / folder
    d.mkdir()
    (d / "template.yaml").write_text(body)


def test_discovery_skips_invalid_and_keeps_valid(tmp_path):
    _write(tmp_path, "ok", VALID)
    _write(tmp_path, "broken", INVALID)

    registry = TemplateRegistry(tmp_path, TemplateLoader(default_registry)).discover()

    # Valid template loads; invalid one is skipped (not a crash).
    assert registry.ids() == ["test.ok"]
    # The skip is recorded for visibility.
    errors = registry.errors()
    assert len(errors) == 1
    assert "this_analyzer_does_not_exist" in next(iter(errors.values()))
