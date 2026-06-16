"""Anonymous auth provider — always returns a guest principal.

PHASE-2: replace with a real provider (validate a JWT / API key / session) and
register it in ``deps.get_principal``. Route handlers that depend on
``get_principal`` need no changes.
"""

from __future__ import annotations

from .base import Principal


class AnonymousAuthProvider:
    def authenticate(self, request=None) -> Principal:
        return Principal(subject="guest", roles=["guest"], is_authenticated=False)
