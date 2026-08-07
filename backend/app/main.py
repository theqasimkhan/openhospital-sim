"""
OpenHospital Sim – FastAPI application entry point.

Startup order:
  1. configure_logging()
  2. connect_db() / connect_redis()
  3. mount routers, middleware, exception handlers
  4. serve
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError, app_error_handler, unhandled_exception_handler
from app.core.logging import configure_logging, get_logger
from app.db.redis import connect_redis, disconnect_redis
from app.db.session import connect_db, disconnect_db
from app.observability.metrics import MetricsMiddleware

# Configure structured logging as the very first action
configure_logging()
logger = get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "startup",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
    )

    # Connect to external dependencies
    await connect_db()
    await connect_redis()

    yield  # ← application runs here

    # Graceful shutdown
    await disconnect_redis()
    await disconnect_db()

    logger.info("shutdown", app=settings.APP_NAME)


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "AI-powered hospital digital twin simulator. "
            "Provides real-time simulation, optimisation, and forecasting "
            "for hospital operations."
        ),
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if not settings.APP_ENV == "production" else None,
        docs_url=f"{settings.API_V1_PREFIX}/docs" if settings.APP_ENV != "production" else None,
        redoc_url=f"{settings.API_V1_PREFIX}/redoc" if settings.APP_ENV != "production" else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.ALLOWED_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(MetricsMiddleware)

    # ── Exception handlers ────────────────────────────────────────────────────
    app.add_exception_handler(AppError, app_error_handler)          # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore[arg-type]

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app: FastAPI = create_app()


# ── Development runner ────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_config=None,  # structlog owns all logging
        access_log=False,
    )
