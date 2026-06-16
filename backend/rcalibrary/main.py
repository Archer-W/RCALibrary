"""FastAPI application factory.

Mounts the API routers and serves the static frontend. The static mount is added
last so ``/api/*`` routes match before the catch-all static handler.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import deps
from .api import routes_l2, routes_l3, routes_meta, routes_templates
from .config import get_settings
from .errors import register_exception_handlers


def create_app() -> FastAPI:
    settings = get_settings()
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

    app.include_router(routes_meta.router)
    app.include_router(routes_templates.router)
    app.include_router(routes_l2.router)
    app.include_router(routes_l3.router)

    # Build singletons now so template-validation errors surface at startup.
    deps.get_solution_registry()

    # Serve the static frontend at the root (added last; /api/* already matched).
    if settings.frontend_dir.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(settings.frontend_dir), html=True),
            name="frontend",
        )

    return app


app = create_app()
