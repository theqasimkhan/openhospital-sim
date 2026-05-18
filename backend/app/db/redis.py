"""
Async Redis client (redis-py ≥ 5.x with asyncio support).

Usage:
    client = await get_redis()
    await client.set("key", "value", ex=300)
    value = await client.get("key")
"""
from __future__ import annotations

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: Redis | None = None


def _build_client() -> Redis:
    return aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30,
    )


async def connect_redis() -> None:
    global _redis_client
    _redis_client = _build_client()
    try:
        await _redis_client.ping()
        logger.info("redis_connected", host=settings.REDIS_HOST, db=settings.REDIS_DB)
    except RedisConnectionError as exc:  # pragma: no cover
        logger.error("redis_connection_failed", error=str(exc))
        raise


async def disconnect_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()  # type: ignore[attr-defined]
        _redis_client = None
    logger.info("redis_disconnected")


async def get_redis() -> Redis:
    if _redis_client is None:
        raise RuntimeError("Redis client is not initialised – check startup lifespan.")
    return _redis_client
