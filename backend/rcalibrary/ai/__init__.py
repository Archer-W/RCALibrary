"""AI panel mode — natural-language input that builds predefined panels.

Free/offline ``SimulatedAIEngine`` by default (no LLM, no cost). The MCP tool server
+ engine/skill interfaces are the stable seam for the other agent to connect a real
LLM in its own environment. See docs/11-ai-panel-builder.md.
"""

from __future__ import annotations

from .engine import AIPanelEngine, DisabledAIEngine, LLMToolEngine, SimulatedAIEngine
from .llm import FakeLLMClient, LLMClient, LLMReply, OpenAICompatLLMClient

__all__ = [
    "AIPanelEngine",
    "DisabledAIEngine",
    "SimulatedAIEngine",
    "LLMToolEngine",
    "LLMClient",
    "LLMReply",
    "FakeLLMClient",
    "OpenAICompatLLMClient",
]
