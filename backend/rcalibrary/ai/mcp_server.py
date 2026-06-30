"""MCP tool server — the stable, app-owned contract for the AI engine.

Wraps the ``ai/tools.py`` capability surface as MCP tools. This is the durable seam
the user asked for: the panel/data/skill capabilities live behind MCP (stable), and
the AI engine is an MCP *client* (swappable). The in-repo ``SimulatedAIEngine`` calls
the tool surface in-process for a free/offline PoC; the other agent's real LLM client
connects to THIS server over MCP (e.g. via langchain-mcp-adapters) and gets the
identical tools — swapping the engine/LLM never touches this layer.

``mcp`` is an optional dependency (the simulated engine does not need it). Install it
with the ``[ai]`` extra to run/connect this server. See docs/11-ai-panel-builder.md.

Run as a stdio MCP server for an external client:  python -m rcalibrary.ai.mcp_server
"""

from __future__ import annotations

from . import tools


def build_mcp_server(template_registry, engine, principal=None):
    """Build a FastMCP server exposing the panel/skill tools. Raises a clear error
    if the optional ``mcp`` package is not installed."""
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "The 'mcp' package is required to run the MCP tool server. "
            "Install it with: pip install mcp  (or pip install '.[ai]')."
        ) from exc

    server = FastMCP("rcalibrary-panels")

    @server.tool()
    def list_library_panels(template_id: str) -> list:
        """List the predefined panels the AI may build for a template (incl. AI-only)."""
        return tools.list_library_panels(template_registry.get(template_id))

    @server.tool()
    def describe_template(template_id: str) -> dict:
        """Describe a template: its report panels + the optional panel library."""
        return tools.describe_template(template_registry.get(template_id))

    @server.tool()
    def build_panel(
        template_id: str,
        panel_id: str,
        inputs: dict | None = None,
        input_group: str | None = None,
        params: dict | None = None,
    ) -> dict:
        """Build ONE predefined panel with AI-resolved params -> {panel, warnings}."""
        template = template_registry.get(template_id)
        panel, warnings = tools.build_panel(
            engine, template, panel_id, inputs or {}, input_group, params or {}, principal
        )
        return {"panel": panel.model_dump(mode="json"), "warnings": list(warnings)}

    @server.tool()
    def run_skill(name: str, args: dict | None = None) -> dict:
        """Invoke a predefined synthesis skill (e.g. summarize_symptoms)."""
        return tools.run_skill(name, **(args or {}))

    return server


def main() -> None:  # pragma: no cover - manual / external-client entry point
    from ..deps import get_engine, get_principal, get_template_registry

    server = build_mcp_server(get_template_registry(), get_engine(), get_principal())
    server.run()  # stdio transport


if __name__ == "__main__":  # pragma: no cover
    main()
