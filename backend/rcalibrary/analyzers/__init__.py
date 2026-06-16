"""Analyzer registry package.

Importing this package imports ``builtins`` so the built-in analyzers
self-register on ``default_registry``.
"""

from . import builtins  # noqa: F401  (import for side-effect: registration)
from .context import AnalysisContext, AnalysisResult
from .registry import AnalyzerRegistry, analyzer, default_registry

__all__ = [
    "AnalysisContext",
    "AnalysisResult",
    "AnalyzerRegistry",
    "analyzer",
    "default_registry",
]
