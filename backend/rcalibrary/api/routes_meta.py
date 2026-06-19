"""Meta + internal seam routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.base import Principal
from ..config import get_settings
from ..deps import get_principal, get_solution_registry
from ..solutions.base import SolutionInfo
from ..solutions.registry import SolutionRegistry

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/solutions", response_model=list[SolutionInfo])
def list_solutions(registry: SolutionRegistry = Depends(get_solution_registry)):
    """List the three solution levels with their availability."""
    return [s.info() for s in registry.all()]


@router.get("/meta")
def meta():
    """Frontend config surfaced at boot (e.g. whether map panels use online tiles)."""
    return {"map_tiles": get_settings().map_tiles}


@router.get("/_internal/whoami", response_model=Principal)
def whoami(principal: Principal = Depends(get_principal)):
    """Auth seam — returns the current (guest) principal. Real auth fills this in."""
    return principal


@router.get("/_internal/audit/health")
def audit_health():
    """Usage-logging seam — reports the active audit mode."""
    return {"mode": get_settings().audit_mode}
