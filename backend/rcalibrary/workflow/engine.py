"""The template engine — orchestrates one Level-1 run.

Pipeline: validate inputs -> resolve & execute data pulls -> run analysis steps
-> assemble report -> emit audit event.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from ..analyzers.context import AnalysisContext, AnalysisResult
from ..analyzers.registry import AnalyzerRegistry
from ..audit.base import AuditEvent, AuditLogger
from ..auth.base import Principal
from ..datasources.base import DataPullRequest, FetchResult, NeutralFilter
from ..datasources.registry import DataSourceRegistry
from ..errors import AnalysisError, InputValidationError, RCAError
from ..reporting.contract import ReportPayload
from . import report_builder
from .input_validation import validate_inputs
from .models import Template

# Only the ${input.<name>} namespace is interpolated (keeps templates declarative
# and injection-safe — values become typed bind params, never concatenated SQL).
_TOKEN = re.compile(r"\$\{input\.([a-zA-Z0-9_]+)\}")


class TemplateRunResult:
    def __init__(self, report: ReportPayload, warnings: list[str]):
        self.report = report
        self.warnings = warnings


class TemplateEngine:
    def __init__(
        self,
        datasources: DataSourceRegistry,
        analyzers: AnalyzerRegistry,
        audit: AuditLogger,
    ):
        self.datasources = datasources
        self.analyzers = analyzers
        self.audit = audit

    def run(
        self,
        template: Template,
        raw_inputs: dict[str, Any],
        principal: Principal | None = None,
        input_group: str | None = None,
    ) -> TemplateRunResult:
        started = time.perf_counter()
        warnings: list[str] = []

        specs = self._resolve_input_specs(template, input_group)
        inputs = validate_inputs(specs, raw_inputs)
        if template.input_groups:
            # Record which set was chosen so templates/analyzers can branch the
            # workflow's starting point on it (referenced as ${input._input_group}).
            inputs["_input_group"] = input_group

        datasets = self._run_data_pulls(template, inputs)
        analysis_results = self._run_analysis(template, datasets, inputs, warnings)
        report = report_builder.build(template, datasets, analysis_results, warnings)

        self._emit_audit(template, principal, analysis_results, started, "ok", input_group)
        return TemplateRunResult(report=report, warnings=warnings)

    def run_panel(
        self,
        template: Template,
        library_panel,
        raw_inputs: dict[str, Any],
        principal: Principal | None = None,
        input_group: str | None = None,
        params: dict[str, Any] | None = None,
    ):
        """Compute ONE optional library panel on demand. Runs the template's main
        pulls/analysis (so the panel can chain on them via ``ctx.results``) plus the
        library bundle's own pulls/analysis, then builds just that panel. Returns
        ``(PanelPayload, warnings)``.

        ``params`` (optional) are AI-resolved knobs (e.g. ``date_start`` / ``date_end``
        / ``granularity``) overlaid onto the bundle's analysis steps' ``.params`` so
        analyzers read them via ``ctx.params``. Unknown keys are ignored by analyzers.

        Done over an ephemeral *merged* template so the existing helpers
        (``analysis_by_id`` / ``data_pull_by_id`` / anomaly resolution) resolve the
        bundle's pulls/steps transparently. model_copy does not re-validate, so the
        already-validated bundle objects pass through untouched."""
        started = time.perf_counter()
        warnings: list[str] = []
        specs = self._resolve_input_specs(template, input_group)
        inputs = validate_inputs(specs, raw_inputs)
        if template.input_groups:
            inputs["_input_group"] = input_group

        bundle_steps = list(library_panel.analysis)
        if params:
            # Overlay AI-resolved params onto each bundle step (the step keeps its
            # own YAML params; the overlay wins). model_copy keeps the originals
            # untouched so a cached/shared template object is never mutated.
            bundle_steps = [s.model_copy(update={"params": {**s.params, **params}}) for s in bundle_steps]
        merged = template.model_copy(
            update={
                "data_pulls": list(template.data_pulls) + list(library_panel.data_pulls),
                "analysis": list(template.analysis) + bundle_steps,
            }
        )
        datasets = self._run_data_pulls(merged, inputs)
        analysis_results = self._run_analysis(merged, datasets, inputs, warnings)
        panel = report_builder._build_panel(merged, library_panel.panel, datasets, analysis_results)
        self._emit_audit(template, principal, analysis_results, started, "ok", input_group)
        return panel, warnings

    def _resolve_input_specs(self, template: Template, input_group: str | None):
        """Pick the input specs to validate against: the chosen group, or the
        flat list when the template has no groups."""
        if not template.input_groups:
            return template.inputs
        if not input_group:
            raise InputValidationError({"_input_group": "Select which input set to use."})
        group = next((g for g in template.input_groups if g.key == input_group), None)
        if group is None:
            valid = [g.key for g in template.input_groups]
            raise InputValidationError(
                {"_input_group": f"Unknown input set '{input_group}' (valid: {valid})"}
            )
        return group.inputs

    # -- stages --------------------------------------------------------------
    def _run_data_pulls(self, template: Template, inputs: dict) -> dict[str, FetchResult]:
        datasets: dict[str, FetchResult] = {}
        for pull in template.data_pulls:
            q = pull.query
            request = DataPullRequest(
                dataset=q.dataset,
                sql=q.sql,
                params=_resolve(q.params, inputs),
                filters=[
                    NeutralFilter(column=f.column, op=f.op, value=_resolve(f.value, inputs))
                    for f in q.filters
                ],
                limit=q.limit,
                columns=pull.columns,
                string_columns=q.string_columns,
                namespace=template.meta.id,
            )
            provider = self.datasources.get(pull.source)
            datasets[pull.id] = provider.fetch(request)
        return datasets

    def _run_analysis(
        self, template: Template, datasets: dict[str, FetchResult], inputs: dict, warnings: list[str]
    ) -> dict[str, AnalysisResult]:
        results: dict[str, AnalysisResult] = {}
        all_frames = {pid: fr.frame for pid, fr in datasets.items()}
        for step in template.analysis:
            fn = self.analyzers.get(step.analyzer)
            frame = datasets[step.inputs["dataset"]].frame
            ctx = AnalysisContext(
                dataset=frame,
                params=_resolve(step.params, inputs),
                inputs=inputs,
                results=results,  # prior steps' results (steps run in order)
                datasets=all_frames,  # every pulled dataset, by pull id
            )
            try:
                results[step.id] = fn(ctx)
            except Exception as exc:  # noqa: BLE001
                if step.on_error == "skip":
                    warnings.append(f"analysis '{step.id}' skipped: {exc}")
                    results[step.id] = AnalysisResult(summary={"error": str(exc)})
                    continue
                if isinstance(exc, RCAError):
                    raise
                raise AnalysisError(f"analysis '{step.id}' failed: {exc}") from exc
        return results

    def _emit_audit(
        self, template, principal, analysis_results, started, status, input_group=None
    ) -> None:
        anomaly_count = sum(len(r.anomalies) for r in analysis_results.values())
        event = AuditEvent(
            event_type="template_run",
            principal_subject=(principal.subject if principal else "guest"),
            template_id=template.meta.id,
            level=template.meta.solution_level,
            status=status,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            anomaly_count=anomaly_count,
            timestamp=datetime.now(timezone.utc).isoformat(),
            extra={"input_group": input_group} if input_group else {},
        )
        self.audit.emit(event)


def _resolve(value: Any, inputs: dict) -> Any:
    """Recursively substitute ${input.<name>} tokens."""
    if isinstance(value, str):
        whole = _TOKEN.fullmatch(value.strip())
        if whole:
            return inputs.get(whole.group(1))
        return _TOKEN.sub(lambda m: str(inputs.get(m.group(1), "")), value)
    if isinstance(value, list):
        return [_resolve(v, inputs) for v in value]
    if isinstance(value, dict):
        return {k: _resolve(v, inputs) for k, v in value.items()}
    return value
