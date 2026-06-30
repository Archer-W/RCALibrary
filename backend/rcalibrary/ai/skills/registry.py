"""Skill registry + the ``@skill`` decorator.

A *skill* is a predefined synthesis capability the AI engine may invoke through the
``run_skill`` tool — e.g. digesting free-text call transcripts into a structured
symptom breakdown. Skills are the only place an LLM would be called in production;
this repo ships **deterministic, offline** implementations (no LLM, no cost). The
other agent overrides a skill by registering an LLM-backed function under the same
name at plugin-load time (last registration wins). Mirrors the analyzer registry.
"""

from __future__ import annotations

from typing import Any, Callable

SkillFn = Callable[..., Any]


class UnknownSkillError(KeyError):
    pass


class SkillRegistry:
    def __init__(self):
        self._fns: dict[str, SkillFn] = {}

    def register(self, name: str, fn: SkillFn) -> None:
        self._fns[name] = fn  # last registration wins (lets the LLM agent override)

    def get(self, name: str) -> SkillFn:
        if name not in self._fns:
            raise UnknownSkillError(f"{name!r} (registered: {self.names()})")
        return self._fns[name]

    def has(self, name: str) -> bool:
        return name in self._fns

    def names(self) -> list[str]:
        return sorted(self._fns)


# Process-wide default registry that built-in skills register into.
default_registry = SkillRegistry()


def skill(name: str) -> Callable[[SkillFn], SkillFn]:
    def deco(fn: SkillFn) -> SkillFn:
        default_registry.register(name, fn)
        return fn

    return deco
