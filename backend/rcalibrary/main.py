"""FastAPI application factory.

Mounts the API routers and serves the static frontend. The static mount is added
last so ``/api/*`` routes match before the catch-all static handler.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import deps, extensions
from .api import routes_l2, routes_l3, routes_meta, routes_templates
from .config import get_settings
from .errors import register_exception_handlers


def create_app() -> FastAPI:
    settings = get_settings()

    # Load use-case plugins FIRST, so their analyzers / data sources / auth
    # provider register before the registries are built and templates validated.
    if settings.plugins:
        extensions.load_plugins(settings.plugins.split(","))

    app = FastAPI(
        title="RCALibrary",
        version="0.1.0",
        description="Automated network-issue Root Cause Analysis — Level-1 fixed-workflow engine.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.middleware("http")
    async def _revalidate_static(request: Request, call_next):
        """Make the browser revalidate static frontend assets (via ETag) so UI
        edits always show up. StaticFiles sets ETag/Last-Modified but no
        Cache-Control, which lets browsers heuristically serve a stale copy."""
        response = await call_next(request)
        if not request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.include_router(routes_meta.router)
    app.include_router(routes_templates.router)
    app.include_router(routes_l2.router)
    app.include_router(routes_l3.router)

    # Build singletons now so template-validation errors surface at startup.
    deps.get_solution_registry()

    # Optional use-case static assets (e.g. custom panel JS) served at /ext.
    # Mounted before the root catch-all so /ext/* matches first.
    if settings.frontend_ext_dir and settings.frontend_ext_dir.exists():
        app.mount(
            "/ext",
            StaticFiles(directory=str(settings.frontend_ext_dir)),
            name="frontend-ext",
        )

    # Serve the static frontend at the root (added last; /api/* already matched).
    if settings.frontend_dir.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(settings.frontend_dir), html=True),
            name="frontend",
        )

    return app


app = create_app()
