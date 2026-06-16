"""Level 2 — LangGraph agentic flow. PLACEHOLDER behind the Solution interface.

PHASE-2: build a LangGraph ``StateGraph`` whose nodes are vetted MCP tools /
scripts; use heuristic next-step selection driven by intermediate findings;
stream results along the search path. ``run()`` would return a SolutionResult
whose ``trace`` records the path. Until then it reports "coming soon" and never
raises.
"""

from __future__ import annotations

from ..auth.base import Principal
from .base import (
    ProblemDescriptor,
    RunRequest,
    Solution,
    SolutionInfo,
    SolutionLevel,
    SolutionResult,
)


class LangGraphSolution(Solution):
    level = SolutionLevel.LANGGRAPH_FLOW

    def info(self) -> SolutionInfo:
        return SolutionInfo(
            level=int(self.level),
            key="langgraph_flow",
            name="Agentic Flow (LangGraph)",
            description=(
                "AI agents traverse a predefined agent graph, using heuristic next-step "
                "search over a bounded set of MCP tools/scripts. Best for complex but "
                "closed problems where the steps are known but the path is data-dependent."
            ),
            status="coming_soon",
            capabilities=[
                "Predefined agent graph (StateGraph)",
                "Heuristic next-step search",
                "Vetted MCP tools / scripts",
                "Result trace along the search path",
            ],
        )

    def list_problems(self) -> list[ProblemDescriptor]:
        return []

    def run(self, request: RunRequest, principal: Principal | None = None) -> SolutionResult:
        return SolutionResult(
            status="not_implemented",
            level=int(self.level),
            message="LangGraph agentic flow is coming soon.",
            escalation_hint=int(SolutionLevel.CLI_AGENT),
        )
