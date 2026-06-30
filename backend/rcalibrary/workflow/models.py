"""The uniform template schema (parsed, validated, in-memory representation).

A template YAML has five sections: ``meta``, ``inputs``, ``data_pulls``,
``analysis``, ``report``. Cross-references are validated here so a malformed
template fails at load time, not at run time. (Analyzer-name existence is checked
by the loader against the analyzer registry.)
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class InputType(str, Enum):
    string = "string"
    int = "int"
    float = "float"
    bool = "bool"
    enum = "enum"
    date = "date"
    datetime = "datetime"


class InputValidation(BaseModel):
    min: float | None = None
    max: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    step: float | None = None


class EnumOption(BaseModel):
    value: str
    label: str


class TemplateInput(BaseModel):
    name: str
    label: str
    type: InputType
    required: bool = True
    default: Any | None = None
    help: str | None = None  # supports **bold** for highlighting words
    placeholder: str | None = None  # example text shown in grey inside the field
    options: list[EnumOption] | None = None
    validation: InputValidation | None = None

    @model_validator(mode="after")
    def _enum_needs_options(self):
        if self.type == InputType.enum and not self.options:
            raise ValueError(f"input '{self.name}' is type=enum but has no options")
        return self


class InputGroup(BaseModel):
    """A mutually-exclusive set of inputs. The UI lets the user pick ONE group;
    only the chosen group's fields are submitted, and the selected group key is
    recorded (so the workflow can branch its starting point on it)."""

    key: str
    label: str
    help: str | None = None
    inputs: list[TemplateInput]


class NeutralFilterSpec(BaseModel):
    column: str
    op: str = "eq"
    value: Any


class DataQuery(BaseModel):
    dataset: str | None = None
    sql: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    filters: list[NeutralFilterSpec] = Field(default_factory=list)
    limit: int | None = None
    # Columns to force to string (e.g. IDs with leading zeros like a USID).
    string_columns: list[str] | None = None

    @model_validator(mode="after")
    def _need_dataset_or_sql(self):
        if not self.dataset and not self.sql:
            raise ValueError("data_pull query needs either 'dataset' or 'sql'")
        return self


class DataPull(BaseModel):
    id: str
    source: str | None = None
    query: DataQuery
    columns: list[str] | None = None


class AnalysisStep(BaseModel):
    id: str
    analyzer: str
    inputs: dict[str, Any] = Field(default_factory=dict)  # must contain "dataset"
    params: dict[str, Any] = Field(default_factory=dict)
    on_error: str = "fail"  # "fail" | "skip"

    @model_validator(mode="after")
    def _need_dataset(self):
        if "dataset" not in self.inputs:
            raise ValueError(f"analysis '{self.id}' must reference inputs.dataset")
        if self.on_error not in ("fail", "skip"):
            raise ValueError(f"analysis '{self.id}' on_error must be 'fail' or 'skip'")
        return self


class PanelType(str, Enum):
    line = "line"
    bar = "bar"
    scatter = "scatter"
    table = "table"
    stat = "stat"
    stat_group = "stat_group"  # several stat cards combined into one panel (options.stats)
    heatmap = "heatmap"
    markdown = "markdown"
    fields = "fields"  # grid of labeled value boxes (one box per value)
    timeseries = "timeseries"  # interactive multi-series chart (USID/granularity toggles)
    map = "map"  # interactive site map (lat/lon markers, ticket tags, layer toggles)
    flow = "flow"  # static workflow / process diagram (stages from options.stages)
    pie = "pie"  # pie/donut distribution chart (labels + values)


class PanelEncoding(BaseModel):
    x: str | None = None
    y: str | None = None
    series: str | None = None
    value: str | None = None
    labels: str | None = None  # pie: column of category labels
    values: str | None = None  # pie: column of numeric values
    columns: list[str] | None = None
    state: str | None = None  # summary key -> "good"|"bad"|"neutral" (colors a stat)
    badge: str | None = None  # summary key -> highlighted pill on a stat (e.g. ticket #)
    detail: str | None = None  # summary key -> prominent secondary line on a stat
    sub: str | None = None  # summary key -> secondary line on a stat
    alert: str | None = None  # summary key -> prominent alert text on a stat


class PanelVisibility(BaseModel):
    """Gate a panel on an analysis result: render only when
    ``analysis_results[ref].summary.get(key)`` is truthy (e.g. Step-1 ``found``)."""

    ref: str  # analysis step id
    key: str  # summary key that must be truthy


class PanelSpec(BaseModel):
    id: str
    type: PanelType
    title: str
    dataset: str | None = None
    analysis_ref: str | None = None
    encoding: PanelEncoding = Field(default_factory=PanelEncoding)
    options: dict[str, Any] = Field(default_factory=dict)
    width: str | None = None  # "full" | "half" | "third"; defaulted by type if unset
    visible_when: PanelVisibility | None = None  # omit the panel unless this holds
    overlay_ref: str | None = None  # pull an overlay (e.g. tickets) from another analysis step


class ReportLayout(BaseModel):
    title: str | None = None
    panels: list[PanelSpec] = Field(default_factory=list)


class ProblemRef(BaseModel):
    """The RCA problem a template addresses. Users browse problems first, then
    pick a template available for the problem. Templates that share a problem id
    are grouped together."""

    id: str
    name: str
    description: str = ""
    domain: str = ""  # e.g. RAN, Core, Transport, Demo
    tags: list[str] = Field(default_factory=list)  # descriptive labels shown on the problem card


class WorkflowStage(BaseModel):
    """One stage in a template's informational triage flow. More than one `step`
    means those steps run in parallel within the stage."""

    title: str = ""
    steps: list[str] = Field(default_factory=list)


class WorkflowInfo(BaseModel):
    """An informational process/triage diagram shown on the template's input page
    (before the user runs it) — not a report panel."""

    caption: str = ""
    stages: list[WorkflowStage] = Field(default_factory=list)


class TemplateMeta(BaseModel):
    id: str
    name: str
    description: str = ""
    version: str = "0.1.0"
    solution_level: int = 1
    tags: list[str] = Field(default_factory=list)
    problem: ProblemRef | None = None
    workflow: WorkflowInfo | None = None  # informational triage flow on the input page
    # Reserved: when true, the "add panel" picker offers an AI-chat option that asks
    # an agent to build a panel from a free-text request (future fixed+agentic
    # template). Default false -> users add only from the predefined library. See docs/10.
    ai_panels: bool = False


class LibraryPanel(BaseModel):
    """An *optional* panel a user can add to a report on demand (not loaded by
    default). Self-contained: it carries its own (lazily-run) data_pulls + analysis
    steps; those steps may chain on the template's main analysis results via
    ``ctx.results``. Computed only when the user adds it. See docs/10."""

    id: str
    title: str
    description: str = ""
    panel: PanelSpec
    data_pulls: list[DataPull] = Field(default_factory=list)
    analysis: list[AnalysisStep] = Field(default_factory=list)
    # When true the panel can only be built via the AI chat (it needs natural-
    # language input and/or a text-synthesis skill). Such panels are hidden from
    # the manual "add panel" picker and rejected by the plain /panel endpoint;
    # the AI engine may select them. See docs/11-ai-panel-builder.md.
    requires_ai: bool = False


class Template(BaseModel):
    meta: TemplateMeta
    # A template uses either a flat `inputs` list, or `input_groups` (mutually
    # exclusive sets the user chooses between). If both are given, groups win.
    inputs: list[TemplateInput] = Field(default_factory=list)
    input_groups: list[InputGroup] = Field(default_factory=list)
    data_pulls: list[DataPull]
    analysis: list[AnalysisStep] = Field(default_factory=list)
    report: ReportLayout
    # Optional panels users can add on demand from a per-problem library.
    panel_library: list[LibraryPanel] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_input_groups(self):
        keys = [g.key for g in self.input_groups]
        if len(keys) != len(set(keys)):
            raise ValueError("input_groups keys must be unique")
        return self

    @model_validator(mode="after")
    def _check_cross_refs(self):
        pull_ids = {p.id for p in self.data_pulls}
        analysis_ids = {a.id for a in self.analysis}

        for step in self.analysis:
            ds = step.inputs.get("dataset")
            if ds not in pull_ids:
                raise ValueError(
                    f"analysis '{step.id}' references unknown dataset '{ds}' "
                    f"(known data_pulls: {sorted(pull_ids)})"
                )
        for panel in self.report.panels:
            if panel.dataset is not None and panel.dataset not in pull_ids:
                raise ValueError(
                    f"panel '{panel.id}' references unknown dataset '{panel.dataset}'"
                )
            if panel.analysis_ref is not None and panel.analysis_ref not in analysis_ids:
                raise ValueError(
                    f"panel '{panel.id}' references unknown analysis '{panel.analysis_ref}'"
                )

        # Library panels: ids must be unique and not clash with report panels; each
        # bundle's refs resolve against the UNION of main + that bundle's pulls/steps
        # (a library analysis step may chain on a main step via ctx.results).
        report_panel_ids = {p.id for p in self.report.panels}
        seen_lib: set[str] = set()
        for lib in self.panel_library:
            if lib.id in seen_lib or lib.id in report_panel_ids:
                raise ValueError(f"library panel id '{lib.id}' is duplicated or clashes with a report panel")
            seen_lib.add(lib.id)
            # A bundle's own pull/step ids must NOT collide with the main template's
            # — run_panel concatenates the lists, and a dict-keyed collision would
            # silently overwrite the main dataset/result.
            for p in lib.data_pulls:
                if p.id in pull_ids:
                    raise ValueError(f"library '{lib.id}' data_pull '{p.id}' collides with a main data_pull id")
            for a in lib.analysis:
                if a.id in analysis_ids:
                    raise ValueError(f"library '{lib.id}' analysis '{a.id}' collides with a main analysis id")
            u_pulls = pull_ids | {p.id for p in lib.data_pulls}
            u_steps = analysis_ids | {a.id for a in lib.analysis}
            for step in lib.analysis:
                ds = step.inputs.get("dataset")
                if ds not in u_pulls:
                    raise ValueError(
                        f"library '{lib.id}' analysis '{step.id}' references unknown dataset '{ds}'"
                    )
            p = lib.panel
            if p.dataset is not None and p.dataset not in u_pulls:
                raise ValueError(f"library '{lib.id}' panel references unknown dataset '{p.dataset}'")
            for ref in (p.analysis_ref, p.overlay_ref):
                if ref is not None and ref not in u_steps:
                    raise ValueError(f"library '{lib.id}' panel references unknown analysis '{ref}'")
        return self

    # convenience lookups -----------------------------------------------------
    def analysis_by_id(self, step_id: str) -> AnalysisStep | None:
        return next((a for a in self.analysis if a.id == step_id), None)

    def data_pull_by_id(self, pull_id: str) -> DataPull | None:
        return next((p for p in self.data_pulls if p.id == pull_id), None)

    def library_panel_by_id(self, lib_id: str) -> LibraryPanel | None:
        return next((b for b in self.panel_library if b.id == lib_id), None)
