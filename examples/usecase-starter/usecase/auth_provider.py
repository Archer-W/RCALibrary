"""Example auth provider. Replace with your real authentication.

The framework calls authenticate() per request and uses the returned Principal
(subject/roles/is_authenticated) for the audit log and future role checks. For
header/token-based auth you will typically also add a FastAPI dependency and may
request a small framework hook to pass the request into authenticate().
"""

from __future__ import annotations

from rcalibrary.auth.base import Principal


class ExampleAuthProvider:
    def __init__(self, default_roles=None):
        self.default_roles = default_roles or ["operator"]

    def authenticate(self, request=None) -> Principal:
        # Placeholder: returns an authenticated service principal. Replace with
        # real validation (JWT / API key / SSO).
        return Principal(subject="svc", roles=self.default_roles, is_authenticated=True)
