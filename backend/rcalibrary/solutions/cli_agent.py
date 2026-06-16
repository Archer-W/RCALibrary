"""Level 3 — CLI super-agent. PLACEHOLDER behind the Solution interface.

PHASE-2: a Claude Code-style agent equipped with skills (the natural consumer of
the sibling NetSkills knowledge base), with sandboxed DB / MCP / API access. It
triages open-ended problems, writes & runs analysis scripts, and reasons over
the output. ``run()`` would return a defended hypothesis + evidence (and capture
a transcript in ``trace`` for reproducibility). Until then it reports "coming
soon" and never raises.
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


class CliAgentSolution(Solution):
    level = SolutionLevel.CLI_AGENT

    def info(self) -> SolutionInfo:
        return SolutionInfo(
            level=int(self.level),
            key="cli_agent",
            name="CLI Super-Agent",
            description=(
                "A CLI agent equipped with skills to triage open-ended problems. It has "
                "backend DB / MCP / API access, writes and runs analysis scripts, and "
                "reasons over the output. Best for novel, exploratory investigations."
            ),
            status="coming_soon",
            capabilities=[
                "Skills-equipped triage (NetSkills)",
                "DB / MCP / API access",
                "Writes & runs analysis scripts",
                "Reasons over live output",
            ],
        )

    def list_problems(self) -> list[ProblemDescriptor]:
        return []

    def run(self, request: RunRequest, principal: Principal | None = None) -> SolutionResult:
        return SolutionResult(
            status="not_implemented",
            level=int(self.level),
            message="CLI super-agent is coming soon.",
        )
