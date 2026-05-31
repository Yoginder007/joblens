"""
Domain exceptions + FastAPI handlers.

Services raise these (transport-agnostic); handlers translate them to HTTP so
business logic never imports ``HTTPException``.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 500
    detail = "Internal server error"

    def __init__(self, detail: str | None = None):
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    detail = "Resource conflict"


class ValidationError(AppError):
    status_code = 422
    detail = "Validation failed"


class AuthError(AppError):
    status_code = 401
    detail = "Unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    detail = "Forbidden"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception on %s", request.url.path, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please try again later."},
        )
