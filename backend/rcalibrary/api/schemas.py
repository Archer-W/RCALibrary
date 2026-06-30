"""API request/response DTOs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..reporting.contract import PanelPayload
from ..workflow.models import InputGroup, TemplateInput, TemplateMeta


class RunBody(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    input_group: str | None = None  # which input set was chosen (grouped templates)
    refresh: bool = False  # recompute even if a saved report exists for this key


class PanelRequest(BaseModel):
    """Add one optional library panel to a report, computed on demand."""

    panel_id: str  # id of the panel_library entry to compute
    inputs: dict[str, Any] = Field(default_factory=dict)
    input_group: str | None = None


class PanelResponse(BaseModel):
    panel: PanelPayload
    warnings: list[str] = Field(default_factory=list)


class AIPanelRequest(BaseModel):
    """One turn of the AI 'build a panel' chat (multi-turn via session_id)."""

    message: str
    session_id: str | None = None  # omit on the first turn; echo it back after
    inputs: dict[str, Any] = Field(default_factory=dict)
    input_group: str | None = None


class AIPanelResponse(BaseModel):
    session_id: str
    # needs_input (clarifying question) | panel (built) | cannot_satisfy | disabled
    status: str
    reply: str
    panel: PanelPayload | None = None
    warnings: list[str] = Field(default_factory=list)


class SaveReportBody(BaseModel):
    """Persist the user's customized report (panels + layout) under the search key."""

    inputs: dict[str, Any] = Field(default_factory=dict)
    input_group: str | None = None
    report: dict[str, Any]  # client-assembled ReportPayload-shaped blob


class SaveResponse(BaseModel):
    key: str
    saved: bool = True


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


class PanelLibraryPreview(BaseModel):
    """An optional panel offered in the 'add panel' picker (compute on demand)."""

    id: str
    title: str
    description: str = ""
    type: str
    requires_ai: bool = False  # AI-only panels are hidden from the manual picker


class TemplateDetail(BaseModel):
    meta: TemplateMeta
    inputs: list[TemplateInput]
    input_groups: list[InputGroup] = Field(default_factory=list)
    report_preview: list[PanelPreview]
    panel_library: list[PanelLibraryPreview] = Field(default_factory=list)
    ai_panels: bool = False  # whether the AI-chat 'add panel' option is offered


class L2RunBody(BaseModel):
    problem: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class L3SessionBody(BaseModel):
    goal: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
