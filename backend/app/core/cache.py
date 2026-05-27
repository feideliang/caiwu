"""Redis cache utilities: cache-aside pattern with pattern invalidation.

Gracefully degrades to no-op when Redis is unavailable, with automatic
recovery via TTL-based retry (30s) to prevent permanent cache bypass.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

# ── Client ────────────────────────────────────────────────────

_redis_client: redis.Redis | None = None
_redis_failed_at: float | None = None  # timestamp of last failure
_REDIS_RETRY_INTERVAL = 30  # seconds before retrying after failure


async def get_redis() -> redis.Redis | None:
    """Return the async Redis client, or None if unavailable.

    Retries connection every _REDIS_RETRY_INTERVAL seconds after a failure,
    instead of permanently disabling cache (fixes silent permanent degradation).
    """
    global _redis_client, _redis_failed_at
    # If previously failed, check if retry interval has elapsed
    if _redis_failed_at is not None:
        if time.monotonic() - _redis_failed_at < _REDIS_RETRY_INTERVAL:
            return None
        logger.info("Redis: retry interval elapsed, attempting reconnection")
        _redis_failed_at = None
    if _redis_client is None:
        try:
            _redis_client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=20,
                socket_connect_timeout=1,
                socket_timeout=2,
            )
            await _redis_client.ping()
        except Exception as exc:
            _redis_failed_at = time.monotonic()
            _redis_client = None
            logger.warning("Redis unavailable, cache disabled for %ds: %s", _REDIS_RETRY_INTERVAL, exc)
            return None
    return _redis_client


async def close_redis() -> None:
    global _redis_client, _redis_failed_at
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        _redis_failed_at = time.monotonic()


# ── Cache helpers ─────────────────────────────────────────────

DEFAULT_TTL = 900  # 15 minutes for dashboard cache


async def cache_get(key: str) -> Any | None:
    client = await get_redis()
    if client is None:
        return None
    raw = await client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    client = await get_redis()
    if client is None:
        return
    await client.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_delete(key: str) -> None:
    client = await get_redis()
    if client is None:
        return
    await client.delete(key)


async def cache_delete_pattern(pattern: str) -> None:
    client = await get_redis()
    if client is None:
        return
    async for key in client.scan_iter(match=pattern):
        await client.delete(key)


# ── Cache-aside decorator factory ─────────────────────────────

def cached(key: str, ttl: int = DEFAULT_TTL):
    """Return a decorator that wraps an async function with cache-aside logic.

    Usage::

        @cached(key="dashboard:overview", ttl=300)
        async def get_overview():
            return expensive_db_call()
    """

    def decorator(fn: Callable):
        async def wrapper(*args: Any, bypass_cache: bool = False, **kwargs: Any) -> Any:
            if not bypass_cache:
                cached_value = await cache_get(key)
                if cached_value is not None:
                    return cached_value
            result = await fn(*args, **kwargs)
            await cache_set(key, result, ttl)
            return result

        return wrapper

    return decorator