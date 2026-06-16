"""Solution registry — level -> Solution instance. The API looks solutions up
here and calls the interface; it never branches on level."""

from __future__ import annotations

from ..errors import RCAError
from .base import Solution


class SolutionRegistry:
    def __init__(self):
        self._by_level: dict[int, Solution] = {}

    def register(self, solution: Solution) -> None:
        self._by_level[int(solution.level)] = solution

    def get(self, level: int) -> Solution:
        if int(level) not in self._by_level:
            raise RCAError(f"No solution registered for level {level}")
        return self._by_level[int(level)]

    def all(self) -> list[Solution]:
        return [self._by_level[k] for k in sorted(self._by_level)]
