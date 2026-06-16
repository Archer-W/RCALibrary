import pytest

from rcalibrary.deps import get_engine, get_template_registry
from rcalibrary.errors import InputValidationError


def test_voc_template_has_three_groups():
    template = get_template_registry().get("ana.rca.netcare-voc-trend")
    assert [g.key for g in template.input_groups] == ["trend_id", "usid_date", "incident_id"]
    assert template.inputs == []  # uses groups, not a flat list


def test_resolve_input_specs_picks_the_chosen_group():
    engine = get_engine()
    template = get_template_registry().get("ana.rca.netcare-voc-trend")

    specs = engine._resolve_input_specs(template, "usid_date")
    assert [s.name for s in specs] == ["usid", "date", "search_neighbors"]


def test_resolve_input_specs_requires_a_valid_group():
    engine = get_engine()
    template = get_template_registry().get("ana.rca.netcare-voc-trend")

    with pytest.raises(InputValidationError):
        engine._resolve_input_specs(template, None)  # must choose a set
    with pytest.raises(InputValidationError):
        engine._resolve_input_specs(template, "does-not-exist")


def test_flat_template_ignores_input_group():
    engine = get_engine()
    template = get_template_registry().get("ana.rca.generic-demo")
    # flat template -> input specs are the flat list regardless of input_group
    specs = engine._resolve_input_specs(template, None)
    assert [s.name for s in specs] == ["node_id", "lookback_hours", "latency_slo_ms"]
