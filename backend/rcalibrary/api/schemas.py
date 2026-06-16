"""API request/response DTOs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..workflow.models import InputGroup, TemplateInput, TemplateMeta


class RunBody(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    input_group: str | None = None  # which input set was chosen (grouped templates)


class TemplateSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    version: str = "0.1.0"
    tags: list[str] = Field(default_factory=list)


class ApproachTemplate(BaseModel):
    """A template offered for a problem, annotated with its approach (level)."""

    id: str
    name: str
    description: str = ""
    version: str = "0.1.0"
    tags: list[str] = Field(default_factory=list)
    level: int
    approach_key: str  # fixed_workflow | langgraph_flow | cli_agent
    approach_name: str  # "Fixed Workflow" | ...
    status: str  # available | coming_soon


class ProblemSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    domain: str = ""
    tags: list[str] = Field(default_factory=list)
    templates: list[ApproachTemplate] = Field(default_factory=list)


class PanelPreview(BaseModel):
    id: str
    type: str
    title: str


class TemplateDetail(BaseModel):
    meta: TemplateMeta
    inputs: list[TemplateInput]
    input_groups: list[InputGroup] = Field(default_factory=list)
    report_preview: list[PanelPreview]


class L2RunBody(BaseModel):
    problem: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class L3SessionBody(BaseModel):
    goal: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
