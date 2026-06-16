"""Domain exceptions + FastAPI exception handlers.

Keeping these in one place lets the engine raise meaningful errors that the API
layer maps to appropriate HTTP status codes, without the engine importing
FastAPI.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class RCAError(Exception):
    """Base class for all RCALibrary domain errors."""


class TemplateNotFoundError(RCAError):
    pass


class TemplateValidationError(RCAError):
    """A template file is structurally invalid (bad refs, unknown analyzer, ...)."""


class InputValidationError(RCAError):
    """User-supplied template inputs failed validation.

    Carries a ``{field: message}`` map so the API can return 422 detail.
    """

    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__(f"Invalid inputs: {errors}")


class DataSourceError(RCAError):
    pass


class UnknownAnalyzerError(RCAError):
    pass


class AnalysisError(RCAError):
    pass


class NotImplementedFeatureError(RCAError):
    """A solution level (or feature) is not implemented yet."""


def register_exception_handlers(app) -> None:
    """Attach handlers that translate domain errors into HTTP responses."""

    @app.exception_handler(TemplateNotFoundError)
    async def _not_found(_: Request, exc: TemplateNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InputValidationError)
    async def _invalid_inputs(_: Request, exc: InputValidationError):
        return JSONResponse(status_code=422, content={"detail": "Invalid inputs", "errors": exc.errors})

    @app.exception_handler(TemplateValidationError)
    async def _bad_template(_: Request, exc: TemplateValidationError):
        return JSONResponse(status_code=500, content={"detail": f"Template error: {exc}"})

    @app.exception_handler(DataSourceError)
    async def _datasource(_: Request, exc: DataSourceError):
        return JSONResponse(status_code=502, content={"detail": f"Data source error: {exc}"})

    @app.exception_handler(UnknownAnalyzerError)
    async def _unknown_analyzer(_: Request, exc: UnknownAnalyzerError):
        return JSONResponse(status_code=500, content={"detail": f"Unknown analyzer: {exc}"})

    @app.exception_handler(AnalysisError)
    async def _analysis(_: Request, exc: AnalysisError):
        return JSONResponse(status_code=500, content={"detail": f"Analysis error: {exc}"})

    @app.exception_handler(NotImplementedFeatureError)
    async def _not_impl(_: Request, exc: NotImplementedFeatureError):
        return JSONResponse(status_code=501, content={"detail": str(exc)})
