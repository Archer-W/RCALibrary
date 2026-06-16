"""Discover, parse, and validate template YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from ..analyzers.registry import AnalyzerRegistry
from ..errors import TemplateValidationError
from .models import Template


class TemplateLoader:
    """Loads a single ``template.yaml`` into a validated ``Template``.

    Also verifies every referenced analyzer name exists in the registry (a check
    that needs the registry and so lives here rather than on the model).
    """

    def __init__(self, analyzers: AnalyzerRegistry):
        self.analyzers = analyzers

    def load_file(self, path: Path) -> Template:
        path = Path(path)
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise TemplateValidationError(f"{path}: invalid YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise TemplateValidationError(f"{path}: template must be a YAML mapping")

        try:
            template = Template.model_validate(raw)
        except ValidationError as exc:
            raise TemplateValidationError(f"{path}: {exc}") from exc

        self._check_analyzers(template, path)
        return template

    def _check_analyzers(self, template: Template, path: Path) -> None:
        for step in template.analysis:
            if not self.analyzers.has(step.analyzer):
                raise TemplateValidationError(
                    f"{path}: analysis '{step.id}' uses unknown analyzer "
                    f"'{step.analyzer}' (registered: {self.analyzers.names()})"
                )
