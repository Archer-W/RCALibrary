"""Template registry — discovers ``templates/*/template.yaml`` and builds a
deterministic (alphabetical, byte-stable) index, mirroring NetSkills' MANIFEST.

There is no central list to edit: drop a template folder in and it appears.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import TemplateNotFoundError
from .loader import TemplateLoader
from .models import Template


class TemplateRegistry:
    def __init__(self, templates_dir: Path, loader: TemplateLoader):
        self.templates_dir = Path(templates_dir)
        self.loader = loader
        self._templates: dict[str, Template] = {}

    def discover(self) -> "TemplateRegistry":
        """Scan the templates dir and load every ``template.yaml``.

        Raises on the first invalid template so problems surface at startup.
        """
        self._templates.clear()
        if not self.templates_dir.exists():
            return self
        for yaml_path in sorted(self.templates_dir.glob("*/template.yaml")):
            template = self.loader.load_file(yaml_path)
            self._templates[template.meta.id] = template
        return self

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
