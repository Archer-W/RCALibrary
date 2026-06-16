"""Level 1 — the fixed-workflow solution (concrete). Wraps the template engine."""

from __future__ import annotations

from ..auth.base import Principal
from ..workflow.engine import TemplateEngine
from ..workflow.registry import TemplateRegistry
from .base import (
    ProblemDescriptor,
    RunRequest,
    Solution,
    SolutionInfo,
    SolutionLevel,
    SolutionResult,
)


class FixedWorkflowSolution(Solution):
    level = SolutionLevel.FIXED_WORKFLOW

    def __init__(self, templates: TemplateRegistry, engine: TemplateEngine):
        self.templates = templates
        self.engine = engine

    def info(self) -> SolutionInfo:
        return SolutionInfo(
            level=int(self.level),
            key="fixed_workflow",
            name="Fixed Workflow",
            description=(
                "Predefined template runbooks. Fill in the inputs; the workflow pulls "
                "data, runs analysis, highlights anomalies, and renders charts. Best for "
                "deterministic, closed problems."
            ),
            status="available",
            capabilities=[
                "YAML-defined templates",
                "Deterministic, reproducible reports",
                "Threshold + statistical anomaly detection",
                "Reusable Plotly panels",
            ],
        )

    def list_problems(self) -> list[ProblemDescriptor]:
        return [
            ProblemDescriptor(
                id=t.meta.id,
                name=t.meta.name,
                description=t.meta.description,
                version=t.meta.version,
                tags=t.meta.tags,
            )
            for t in self.templates.list()
        ]

    def run(self, request: RunRequest, principal: Principal | None = None) -> SolutionResult:
        template = self.templates.get(request.template_id)
        result = self.engine.run(
            template, request.inputs, principal, input_group=request.input_group
        )
        return SolutionResult(
            status="ok",
            level=int(self.level),
            report=result.report,
            warnings=result.warnings,
        )
