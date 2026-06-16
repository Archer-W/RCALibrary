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
    heatmap = "heatmap"
    markdown = "markdown"


class PanelEncoding(BaseModel):
    x: str | None = None
    y: str | None = None
    series: str | None = None
    value: str | None = None
    columns: list[str] | None = None


class PanelSpec(BaseModel):
    id: str
    type: PanelType
    title: str
    dataset: str | None = None
    analysis_ref: str | None = None
    encoding: PanelEncoding = Field(default_factory=PanelEncoding)
    options: dict[str, Any] = Field(default_factory=dict)
    width: str | None = None  # "full" | "half" | "third"; defaulted by type if unset


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


class TemplateMeta(BaseModel):
    id: str
    name: str
    description: str = ""
    version: str = "0.1.0"
    solution_level: int = 1
    tags: list[str] = Field(default_factory=list)
    problem: ProblemRef | None = None


class Template(BaseModel):
    meta: TemplateMeta
    # A template uses either a flat `inputs` list, or `input_groups` (mutually
    # exclusive sets the user chooses between). If both are given, groups win.
    inputs: list[TemplateInput] = Field(default_factory=list)
    input_groups: list[InputGroup] = Field(default_factory=list)
    data_pulls: list[DataPull]
    analysis: list[AnalysisStep] = Field(default_factory=list)
    report: ReportLayout

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
        return self

    # convenience lookups -----------------------------------------------------
    def analysis_by_id(self, step_id: str) -> AnalysisStep | None:
        return next((a for a in self.analysis if a.id == step_id), None)

    def data_pull_by_id(self, pull_id: str) -> DataPull | None:
        return next((p for p in self.data_pulls if p.id == pull_id), None)
