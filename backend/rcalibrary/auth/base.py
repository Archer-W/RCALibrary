"""Auth interfaces. PLACEHOLDER — see ``anonymous.py`` for the only implementation today."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class Principal(BaseModel):
    """The authenticated (or anonymous) caller."""

    subject: str = "guest"
    roles: list[str] = Field(default_factory=lambda: ["guest"])
    is_authenticated: bool = False


@runtime_checkable
class AuthProvider(Protocol):
    def authenticate(self, request=None) -> Principal:  # noqa: D401
        ...
