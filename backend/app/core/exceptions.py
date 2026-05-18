from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Domain exceptions ─────────────────────────────────────────────────────────

class AppError(Exception):
    """Base application error – always maps to an HTTP response."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        detail: Any = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.detail = detail
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"
    message = "The requested resource was not found."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"
    message = "A resource conflict occurred."


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"
    message = "Input validation failed."


class SimulationError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "SIMULATION_ERROR"
    message = "The simulation engine encountered an error."


# ── Exception handlers ────────────────────────────────────────────────────────

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "application_error",
        error_code=exc.error_code,
        status_code=exc.status_code,
        message=exc.message,
        path=str(request.url),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        path=str(request.url),
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected server error occurred.",
            "detail": None,
        },
    )
