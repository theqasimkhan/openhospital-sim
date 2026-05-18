"""
Reusable FastAPI dependencies.

Import these ``Annotated`` aliases directly in route signatures:

    async def my_route(db: DBSession, redis: RedisClient) -> ...:
        ...
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.db.session import get_db

# ── Database ──────────────────────────────────────────────────────────────────
DBSession = Annotated[AsyncSession, Depends(get_db)]

# ── Redis ─────────────────────────────────────────────────────────────────────
RedisClient = Annotated[Redis, Depends(get_redis)]
