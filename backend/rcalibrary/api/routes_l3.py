"""Level-3 (CLI super-agent) placeholder routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from ..auth.base import Principal
from ..deps import get_principal, get_solution_registry
from ..solutions.base import RunRequest, SolutionInfo, SolutionLevel, SolutionResult
from ..solutions.registry import SolutionRegistry
from .schemas import L3SessionBody

router = APIRouter(prefix="/api/l3", tags=["cli-agent"])


@router.get("/info", response_model=SolutionInfo)
def l3_info(solutions: SolutionRegistry = Depends(get_solution_registry)):
    return solutions.get(int(SolutionLevel.CLI_AGENT)).info()


@router.post("/session", response_model=SolutionResult)
def l3_session(
    body: L3SessionBody,
    response: Response,
    solutions: SolutionRegistry = Depends(get_solution_registry),
    principal: Principal = Depends(get_principal),
):
    result = solutions.get(int(SolutionLevel.CLI_AGENT)).run(
        RunRequest(problem=body.goal, context=body.constraints), principal
    )
    if result.status == "not_implemented":
        response.status_code = 501
    return result
