"""The AI tool surface — the STABLE capability layer the AI engine calls.

These plain functions are the contract: discover the predefined panels, describe a
template, build one panel with AI-resolved params, and run a synthesis skill. The
in-repo ``SimulatedAIEngine`` calls them in-process; ``ai/mcp_server.py`` wraps the
SAME functions as MCP tools so the other agent's real LLM client reaches an
identical surface over MCP. Swapping the engine never changes this layer. The
engine **only calls these tools** — it never generates code or new panels.
"""

from __future__ import annotations

from typing import Any

# Panel types whose data window/resolution can be tuned by AI params.
_PARAMETERIZED = {"timeseries", "line", "bar", "scatter"}


def panel_params(panel_spec) -> list[str]:
    """Which AI knobs a panel accepts (so the agent knows what to extract)."""
    if panel_spec.type.value in _PARAMETERIZED:
        return ["date_start", "date_end", "granularity"]
    return []


def list_library_panels(template) -> list[dict[str, Any]]:
    """The predefined panels the AI may build for this template (incl. AI-only ones)."""
    return [
        {
            "id": b.id,
            "title": b.title,
            "description": b.description,
            "type": b.panel.type.value,
            "requires_ai": b.requires_ai,
            "params": panel_params(b.panel),
        }
        for b in template.panel_library
    ]


def describe_template(template) -> dict[str, Any]:
    """A compact catalog the agent reads to ground its choices."""
    return {
        "id": template.meta.id,
        "name": template.meta.name,
        "description": template.meta.description,
        "report_panels": [
            {"id": p.id, "type": p.type.value, "title": p.title} for p in template.report.panels
        ],
        "library": list_library_panels(template),
    }


def build_panel(engine, template, panel_id, inputs, input_group, params, principal):
    """Build ONE predefined library panel with AI-resolved params. Returns
    ``(PanelPayload, warnings)``. Raises ``KeyError`` for an unknown panel id."""
    bundle = template.library_panel_by_id(panel_id)
    if bundle is None:
        raise KeyError(panel_id)
    return engine.run_panel(
        template, bundle, inputs, principal, input_group=input_group, params=params
    )


def run_skill(name: str, **args):
    """Invoke a predefined synthesis skill by name (e.g. ``summarize_symptoms``)."""
    from .skills import default_registry

    return default_registry.get(name)(**args)
