"""Solution interface + shared request/result models.

All three levels (fixed workflow, LangGraph flow, CLI super-agent) implement
``Solution``. Level 1 is concrete; levels 2 and 3 are clean placeholders behind
the same interface, so the API never branches on level.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field

from ..auth.base import Principal
from ..reporting.contract import ReportPayload


class SolutionLevel(IntEnum):
    FIXED_WORKFLOW = 1
    LANGGRAPH_FLOW = 2
    CLI_AGENT = 3


class ProblemDescriptor(BaseModel):
    """A runnable problem within a solution (for L1, a template)."""

    id: str
    name: str
    description: str = ""
    version: str = "0.1.0"
    tags: list[str] = Field(default_factory=list)


class SolutionInfo(BaseModel):
    level: int
    key: str
    name: str
    description: str
    status: str  # "available" | "coming_soon"
    capabilities: list[str] = Field(default_factory=list)


class RunRequest(BaseModel):
    # L1 uses template_id + inputs; L2/L3 reserve problem + context.
    template_id: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    # For templates with input_groups: which set the user chose.
    input_group: str | None = None
    problem: str | None = None
    # seed_context carried forward on escalation (prior inputs / pulled data / findings).
    context: dict[str, Any] = Field(default_factory=dict)


class SolutionResult(BaseModel):
    status: str  # "ok" | "inconclusive" | "not_implemented" | "error"
    level: int
    message: str | None = None
    report: ReportPayload | None = None
    escalation_hint: int | None = None  # suggested next level
    trace: list[dict] = Field(default_factory=list)  # L2 search path / L3 transcript (later)
    warnings: list[str] = Field(default_factory=list)


class Solution(ABC):
    level: SolutionLevel

    @abstractmethod
    def info(self) -> SolutionInfo: ...

    @abstractmethod
    def list_problems(self) -> list[ProblemDescriptor]: ...

    @abstractmethod
    def run(self, request: RunRequest, principal: Principal | None = None) -> SolutionResult: ...
