"""Level-1 routes: list templates, load a template's form schema, run a template."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from ..ai.engine import AIPanelEngine
from ..auth.base import Principal
from ..deps import (
    get_ai_panel_engine,
    get_engine,
    get_principal,
    get_report_cache,
    get_solution_registry,
    get_template_registry,
)
from ..persistence.report_cache import ReportCache, ReportCacheError
from ..reporting.contract import ReportPayload
from ..solutions.base import RunRequest, SolutionLevel, SolutionResult
from ..solutions.registry import SolutionRegistry
from ..workflow.engine import TemplateEngine
from ..workflow.registry import TemplateRegistry
from .schemas import (
    AIPanelRequest,
    AIPanelResponse,
    ApproachTemplate,
    PanelLibraryPreview,
    PanelPreview,
    PanelRequest,
    PanelResponse,
    ProblemSummary,
    RunBody,
    SaveReportBody,
    SaveResponse,
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
                tags=list(prob.tags) if prob else [],
            )
        elif prob:
            # Multiple templates can share a problem — union their tags (dedup, ordered).
            for tag in prob.tags:
                if tag not in groups[pid].tags:
                    groups[pid].tags.append(tag)
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
        input_groups=template.input_groups,
        report_preview=[
            PanelPreview(id=p.id, type=p.type.value, title=p.title)
            for p in template.report.panels
        ],
        panel_library=[
            PanelLibraryPreview(
                id=b.id, title=b.title, description=b.description,
                type=b.panel.type.value, requires_ai=b.requires_ai,
            )
            for b in template.panel_library
        ],
        ai_panels=template.meta.ai_panels,
    )


def _cache_scope(template, principal) -> str:
    # Fold the template version + principal into the cache key so a template change
    # invalidates stale saves and saved reports are isolated per tenant.
    subject = principal.subject if principal else "guest"
    return f"{template.meta.version}|{subject}"


@router.post("/templates/{template_id}/run", response_model=SolutionResult)
def run_template(
    template_id: str,
    body: RunBody,
    templates: TemplateRegistry = Depends(get_template_registry),
    solutions: SolutionRegistry = Depends(get_solution_registry),
    principal: Principal = Depends(get_principal),
    cache: ReportCache = Depends(get_report_cache),
):
    template = templates.get(template_id)  # -> 404 if unknown
    scope = _cache_scope(template, principal)
    # Same key + a previously saved report -> load it directly (no recompute),
    # unless the caller asked to refresh. A malformed/stale blob falls through to a
    # fresh compute rather than erroring.
    if not body.refresh:
        saved = cache.get(template_id, body.input_group, body.inputs, scope)
        if saved is not None:
            try:
                report = ReportPayload.model_validate(saved)
            except Exception:  # noqa: BLE001 - bad cache entry -> recompute
                report = None
            if report is not None:
                return SolutionResult(
                    status="ok",
                    level=int(SolutionLevel.FIXED_WORKFLOW),
                    report=report,
                    from_cache=True,
                )
    request = RunRequest(
        template_id=template_id, inputs=body.inputs, input_group=body.input_group
    )
    solution = solutions.get(int(SolutionLevel.FIXED_WORKFLOW))
    return solution.run(request, principal)


@router.post("/templates/{template_id}/panel", response_model=PanelResponse)
def add_panel(
    template_id: str,
    body: PanelRequest,
    templates: TemplateRegistry = Depends(get_template_registry),
    engine: TemplateEngine = Depends(get_engine),
    principal: Principal = Depends(get_principal),
):
    """Compute ONE optional library panel on demand (lazy: it is not part of the
    default report). Returns the single panel payload."""
    template = templates.get(template_id)  # -> 404
    bundle = template.library_panel_by_id(body.panel_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"Unknown library panel '{body.panel_id}'")
    if bundle.requires_ai:
        # AI-only panels need natural-language input — add them via the AI chat.
        raise HTTPException(
            status_code=400,
            detail=f"Panel '{body.panel_id}' is AI-only; build it via the AI chat (/panel/ai).",
        )
    panel, warnings = engine.run_panel(
        template, bundle, body.inputs, principal, input_group=body.input_group
    )
    return PanelResponse(panel=panel, warnings=warnings)


@router.post("/templates/{template_id}/panel/ai", response_model=AIPanelResponse)
async def add_panel_ai(
    template_id: str,
    body: AIPanelRequest,
    templates: TemplateRegistry = Depends(get_template_registry),
    ai: AIPanelEngine = Depends(get_ai_panel_engine),
    principal: Principal = Depends(get_principal),
):
    """One turn of the AI 'build a panel' chat. The engine parses the free-text
    request, picks a predefined library panel, fills params, and builds it — or
    asks a clarifying question / says it can't. Multi-turn via ``session_id``. The
    engine is swappable (simulated here; real LLM in the other agent's env). See
    docs/11-ai-panel-builder.md."""
    template = templates.get(template_id)  # -> 404
    if not template.meta.ai_panels:
        return AIPanelResponse(
            session_id=body.session_id or "",
            status="disabled",
            reply="AI panel building is not enabled for this template.",
        )
    # The engine call is sync (and a real engine would block on the LLM) -> off the
    # event loop. Engines never raise to the route; they return a structured reply.
    result = await run_in_threadpool(
        ai.chat,
        body.session_id,
        body.message,
        template=template,
        inputs=body.inputs,
        input_group=body.input_group,
        principal=principal,
    )
    return AIPanelResponse(**result)


@router.post("/templates/{template_id}/save", response_model=SaveResponse)
def save_report(
    template_id: str,
    body: SaveReportBody,
    templates: TemplateRegistry = Depends(get_template_registry),
    cache: ReportCache = Depends(get_report_cache),
    principal: Principal = Depends(get_principal),
):
    """Persist the user's customized report under the search key so the same key
    reloads it without recompute (see /run)."""
    template = templates.get(template_id)  # validate template exists -> 404
    try:
        key = cache.put(
            template_id, body.input_group, body.inputs, body.report,
            _cache_scope(template, principal),
        )
    except ReportCacheError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    return SaveResponse(key=key, saved=True)
