"""
Async SQLAlchemy session factory for PostgreSQL.

Usage (inside a FastAPI dependency):
    async with async_session() as session:
        result = await session.execute(select(Model))
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Engine ────────────────────────────────────────────────────────────────────

def _build_engine() -> AsyncEngine:
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        connect_args={"server_settings": {"application_name": settings.APP_NAME}},
    )


engine: AsyncEngine = _build_engine()

# ── Session factory ───────────────────────────────────────────────────────────

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Lifecycle helpers ─────────────────────────────────────────────────────────

async def connect_db() -> None:
    """Verify the database connection on startup.

    A failed connection is logged as a critical warning but does NOT crash
    the application. The simulation engine runs entirely in-memory and will
    continue to function without a database. Persistence features (Phase 7)
    will fail gracefully when called.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("database_connected", url=settings.POSTGRES_HOST)
    except Exception as exc:
        logger.warning(
            "database_connection_failed – running without persistence",
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            error=str(exc),
        )


async def disconnect_db() -> None:
    """Dispose engine connection pool on shutdown."""
    await engine.dispose()
    logger.info("database_disconnected")


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
