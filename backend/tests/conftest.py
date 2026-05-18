"""
Pytest configuration and shared fixtures.

The test suite uses an in-process FastAPI ASGI client (httpx.AsyncClient)
with dependency overrides so no real PostgreSQL or Redis instance is required
for the unit tests that ship in this skeleton.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.db.session import get_db
from app.main import app


# ── Mock database session ─────────────────────────────────────────────────────

@pytest.fixture()
def mock_db_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    # Simulate `SELECT 1` returning a truthy result
    session.execute.return_value = MagicMock(scalar=lambda: 1)
    return session


# ── Mock Redis client ─────────────────────────────────────────────────────────

@pytest.fixture()
def mock_redis_client() -> AsyncMock:
    client = AsyncMock()
    client.ping.return_value = True
    return client


# ── Async test client ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def client(
    mock_db_session: AsyncMock,
    mock_redis_client: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield mock_db_session  # type: ignore[misc]

    async def _override_redis() -> AsyncMock:
        return mock_redis_client

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
