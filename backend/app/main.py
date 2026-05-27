"""FastAPI application factory with middleware and lifespan."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.middleware import TraceIDMiddleware
from app.core.response import APIResponse, ErrorCode

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    from app.db.session import close_db, engine, async_session_factory
    from app.core.cache import close_redis

    # Pre-warm database connections (establishes SSL + auth for pool)
    # This prevents 2-3s delay on first request from cold connection setup
    # Pre-warm 5 connections to cover concurrent BFF requests
    try:
        import asyncio as _aio
        from sqlalchemy import text as _text

        async def _warm_one():
            async with async_session_factory() as session:
                await session.execute(_text("SELECT 1"))

        await _aio.gather(*[_warm_one() for _ in range(5)])
        logger.info("Database connection pool pre-warmed (5 connections)")
    except Exception as exc:
        logger.warning("Failed to pre-warm DB connections: %s", exc)

    # Log Celery configuration
    try:
        from app.celery_app import celery_app

        logger.info(
            "Celery app initialized — broker: %s, backend: %s",
            celery_app.conf.broker_url,
            celery_app.conf.result_backend,
        )
        logger.info("Celery queues: %s", list(celery_app.conf.task_queues.keys()))
    except Exception:
        logger.warning("Celery app not available; async tasks will not run")

    yield
    await close_db()
    await close_redis()


def create_app() -> FastAPI:
    """Application factory."""

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # ── Middleware (order matters: innermost first) ───────────

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trace ID + global exception handling
    app.add_middleware(TraceIDMiddleware)

    # ── Routers ───────────────────────────────────────────────

    from app.api.router import api_v1_router

    app.include_router(api_v1_router)

    # ── Health check ──────────────────────────────────────────

    @app.get("/health", tags=["ops"])
    async def health() -> dict:
        return {"status": "ok", "version": settings.app_version}

    @app.get("/", tags=["ops"])
    async def root() -> dict:
        return {"name": settings.app_name, "version": settings.app_version}

    return app


app = create_app()
