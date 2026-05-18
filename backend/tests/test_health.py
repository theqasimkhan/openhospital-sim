"""
Unit tests for /api/v1/ping and /api/v1/health endpoints.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import settings

BASE = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_ping_returns_pong(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "pong"}


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == settings.APP_NAME
    assert body["version"] == settings.APP_VERSION
    assert "postgres" in body["services"]
    assert "redis" in body["services"]
    assert body["services"]["postgres"]["status"] == "ok"
    assert body["services"]["redis"]["status"] == "ok"


@pytest.mark.asyncio
async def test_health_postgres_down(
    client: AsyncClient,
    mock_db_session,
) -> None:
    mock_db_session.execute.side_effect = Exception("connection refused")
    response = await client.get(f"{BASE}/health")
    assert response.status_code == 200  # endpoint itself doesn't 503 for probes
    body = response.json()
    assert body["status"] == "degraded"
    assert body["services"]["postgres"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_health_redis_down(
    client: AsyncClient,
    mock_redis_client,
) -> None:
    mock_redis_client.ping.side_effect = Exception("connection refused")
    response = await client.get(f"{BASE}/health")
    body = response.json()
    assert body["status"] == "degraded"
    assert body["services"]["redis"]["status"] == "unavailable"
