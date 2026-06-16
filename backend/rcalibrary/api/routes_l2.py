"""Level-2 (LangGraph) placeholder routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from ..auth.base import Principal
from ..deps import get_principal, get_solution_registry
from ..solutions.base import RunRequest, SolutionInfo, SolutionLevel, SolutionResult
from ..solutions.registry import SolutionRegistry
from .schemas import L2RunBody

router = APIRouter(prefix="/api/l2", tags=["langgraph"])


@router.get("/info", response_model=SolutionInfo)
def l2_info(solutions: SolutionRegistry = Depends(get_solution_registry)):
    return solutions.get(int(SolutionLevel.LANGGRAPH_FLOW)).info()


@router.post("/run", response_model=SolutionResult)
def l2_run(
    body: L2RunBody,
    response: Response,
    solutions: SolutionRegistry = Depends(get_solution_registry),
    principal: Principal = Depends(get_principal),
):
    result = solutions.get(int(SolutionLevel.LANGGRAPH_FLOW)).run(
        RunRequest(problem=body.problem, context=body.context), principal
    )
    if result.status == "not_implemented":
        response.status_code = 501
    return result
