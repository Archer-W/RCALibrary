"""Analyzer registry + the ``@analyzer`` decorator.

YAML templates reference analyzers by their registered string name. New
analyzers register themselves at import time — no engine changes required.
"""

from __future__ import annotations

from typing import Callable

from ..errors import UnknownAnalyzerError
from .context import AnalysisContext, AnalysisResult

AnalyzerFn = Callable[[AnalysisContext], AnalysisResult]


class AnalyzerRegistry:
    def __init__(self):
        self._fns: dict[str, AnalyzerFn] = {}

    def register(self, name: str, fn: AnalyzerFn) -> None:
        self._fns[name] = fn

    def get(self, name: str) -> AnalyzerFn:
        if name not in self._fns:
            raise UnknownAnalyzerError(f"{name!r} (registered: {self.names()})")
        return self._fns[name]

    def has(self, name: str) -> bool:
        return name in self._fns

    def names(self) -> list[str]:
        return sorted(self._fns)


# The process-wide default registry that built-ins register into.
default_registry = AnalyzerRegistry()


def analyzer(name: str) -> Callable[[AnalyzerFn], AnalyzerFn]:
    def deco(fn: AnalyzerFn) -> AnalyzerFn:
        default_registry.register(name, fn)
        return fn

    return deco
