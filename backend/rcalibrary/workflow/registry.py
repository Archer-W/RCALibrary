"""Template registry — discovers ``templates/*/template.yaml`` and builds a
deterministic (alphabetical, byte-stable) index, mirroring NetSkills' MANIFEST.

There is no central list to edit: drop a template folder in and it appears.

Discovery is **resilient**: a template that fails to load (bad YAML, unknown
analyzer, broken reference) is skipped with a logged warning and recorded in
``errors()`` rather than crashing the whole app. This lets a *placeholder*
template — whose real analyzer or data-source plugin isn't loaded yet — coexist
safely: it simply doesn't appear until it's runnable. (The loader itself still
raises on a single file, which is what the unit tests assert.)
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..errors import TemplateNotFoundError, TemplateValidationError
from .loader import TemplateLoader
from .models import Template

logger = logging.getLogger(__name__)


class TemplateRegistry:
    def __init__(self, templates_dir: Path, loader: TemplateLoader):
        self.templates_dir = Path(templates_dir)
        self.loader = loader
        self._templates: dict[str, Template] = {}
        self._errors: dict[str, str] = {}

    def discover(self) -> "TemplateRegistry":
        """Scan the templates dir and load every ``template.yaml``.

        Invalid / not-yet-runnable templates are skipped (and recorded in
        ``errors()``) instead of aborting startup.
        """
        self._templates.clear()
        self._errors.clear()
        if not self.templates_dir.exists():
            return self
        for yaml_path in sorted(self.templates_dir.glob("*/template.yaml")):
            try:
                template = self.loader.load_file(yaml_path)
            except TemplateValidationError as exc:
                self._errors[str(yaml_path)] = str(exc)
                logger.warning("Skipping template %s: %s", yaml_path, exc)
                continue
            self._templates[template.meta.id] = template
        return self

    def errors(self) -> dict[str, str]:
        """Map of template file -> load error, for templates that were skipped."""
        return dict(self._errors)

    def list(self) -> list[Template]:
        return [self._templates[k] for k in sorted(self._templates)]

    def get(self, template_id: str) -> Template:
        if template_id not in self._templates:
            raise TemplateNotFoundError(
                f"Template '{template_id}' not found (have: {sorted(self._templates)})"
            )
        return self._templates[template_id]

    def ids(self) -> list[str]:
        return sorted(self._templates)
