"""Async SQLAlchemy engine, session, and dependency injection."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=10,
    pool_size=5,
    max_overflow=10,
    pool_use_lifo=True,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    await engine.dispose()


# ── Sync engine/session (for Qdrant upsert outside async context) ──

sync_engine = create_engine(
    settings.sync_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=10,
    pool_size=5,
    max_overflow=10,
)

sync_session_factory = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


def get_sync_session() -> Session:
    """Return a sync SQLAlchemy session (for use outside async context)."""
    return sync_session_factory()
