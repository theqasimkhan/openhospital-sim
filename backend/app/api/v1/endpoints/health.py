from __future__ import annotations

import time
from datetime import datetime

from fastapi import APIRouter, status
from sqlalchemy import text

from app.api.deps import DBSession, RedisClient
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.health import HealthResponse, PingResponse, ServiceStatus

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get(
    "/ping",
    response_model=PingResponse,
    summary="Liveness probe",
    status_code=status.HTTP_200_OK,
)
async def ping() -> PingResponse:
    """Minimal liveness endpoint – no external checks."""
    return PingResponse()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Readiness / health check",
    status_code=status.HTTP_200_OK,
)
async def health_check(
    db: DBSession,
    redis: RedisClient,
) -> HealthResponse:
    """
    Deep health check: probes PostgreSQL and Redis.

    Returns ``200 OK`` when all services are healthy,
    ``503 Service Unavailable`` when any dependency is unreachable.
    """
    services: dict[str, ServiceStatus] = {}
    overall = "ok"

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    try:
        t0 = time.perf_counter()
        await db.execute(text("SELECT 1"))
        latency = round((time.perf_counter() - t0) * 1000, 2)
        services["postgres"] = ServiceStatus(status="ok", latency_ms=latency)
    except Exception as exc:
        logger.warning("health_check_postgres_failed", error=str(exc))
        services["postgres"] = ServiceStatus(status="unavailable", detail=str(exc))
        overall = "degraded"

    # ── Redis ─────────────────────────────────────────────────────────────────
    try:
        t0 = time.perf_counter()
        await redis.ping()
        latency = round((time.perf_counter() - t0) * 1000, 2)
        services["redis"] = ServiceStatus(status="ok", latency_ms=latency)
    except Exception as exc:
        logger.warning("health_check_redis_failed", error=str(exc))
        services["redis"] = ServiceStatus(status="unavailable", detail=str(exc))
        overall = "degraded"

    return HealthResponse(
        status=overall,  # type: ignore[arg-type]
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        timestamp=datetime.utcnow(),
        services=services,
    )
