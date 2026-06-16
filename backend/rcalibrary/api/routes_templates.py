"""Level-1 routes: list templates, load a template's form schema, run a template."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.base import Principal
from ..deps import get_principal, get_solution_registry, get_template_registry
from ..solutions.base import RunRequest, SolutionLevel, SolutionResult
from ..solutions.registry import SolutionRegistry
from ..workflow.registry import TemplateRegistry
from .schemas import (
    ApproachTemplate,
    PanelPreview,
    ProblemSummary,
    RunBody,
    TemplateDetail,
    TemplateSummary,
)

router = APIRouter(prefix="/api", tags=["templates"])


@router.get("/problems", response_model=list[ProblemSummary])
def list_problems(
    templates: TemplateRegistry = Depends(get_template_registry),
    solutions: SolutionRegistry = Depends(get_solution_registry),
):
    """Group available templates by the RCA problem they address.

    This is the primary entry point: users browse problems first, then pick a
    template (annotated with its approach/level) available for the problem.
    """
    groups: dict[str, ProblemSummary] = {}
    for t in templates.list():
        prob = t.meta.problem
        pid = prob.id if prob else t.meta.id
        if pid not in groups:
            groups[pid] = ProblemSummary(
                id=pid,
                name=prob.name if prob else t.meta.name,
                description=prob.description if prob else t.meta.description,
                domain=prob.domain if prob else "",
            )
        groups[pid].templates.append(_approach(t, solutions))
    return [groups[k] for k in sorted(groups)]


def _approach(template, solutions: SolutionRegistry) -> ApproachTemplate:
    level = template.meta.solution_level
    try:
        info = solutions.get(level).info()
        approach_key, approach_name, status = info.key, info.name, info.status
    except Exception:  # noqa: BLE001 - unregistered level -> graceful default
        approach_key, approach_name, status = f"level_{level}", f"Level {level}", "coming_soon"
    return ApproachTemplate(
        id=template.meta.id,
        name=template.meta.name,
        description=template.meta.description,
        version=template.meta.version,
        tags=template.meta.tags,
        level=level,
        approach_key=approach_key,
        approach_name=approach_name,
        status=status,
    )


@router.get("/templates", response_model=list[TemplateSummary])
def list_templates(templates: TemplateRegistry = Depends(get_template_registry)):
    return [
        TemplateSummary(
            id=t.meta.id,
            name=t.meta.name,
            description=t.meta.description,
            version=t.meta.version,
            tags=t.meta.tags,
        )
        for t in templates.list()
    ]


@router.get("/templates/{template_id}", response_model=TemplateDetail)
def get_template(template_id: str, templates: TemplateRegistry = Depends(get_template_registry)):
    template = templates.get(template_id)  # -> 404 via TemplateNotFoundError
    return TemplateDetail(
        meta=template.meta,
        inputs=template.inputs,
        report_preview=[
            PanelPreview(id=p.id, type=p.type.value, title=p.title)
            for p in template.report.panels
        ],
    )


@router.post("/templates/{template_id}/run", response_model=SolutionResult)
def run_template(
    template_id: str,
    body: RunBody,
    solutions: SolutionRegistry = Depends(get_solution_registry),
    principal: Principal = Depends(get_principal),
):
    request = RunRequest(template_id=template_id, inputs=body.inputs)
    solution = solutions.get(int(SolutionLevel.FIXED_WORKFLOW))
    return solution.run(request, principal)
