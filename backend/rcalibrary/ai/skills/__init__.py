"""Predefined synthesis skills the AI engine can invoke (offline, no LLM here)."""

from __future__ import annotations

from .registry import SkillRegistry, UnknownSkillError, default_registry, skill

# Importing the package registers the built-in skills (import-time side effects).
from . import text_synthesis  # noqa: F401  (registers "summarize_symptoms")

__all__ = ["SkillRegistry", "UnknownSkillError", "default_registry", "skill"]
