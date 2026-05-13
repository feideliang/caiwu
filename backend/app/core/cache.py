"""Redis cache utilities: cache-aside pattern with pattern invalidation."""

from __future__ import annotations

import json
from typing import Any, Callable

import redis.asyncio as redis

from app.config import settings

# ── Client ────────────────────────────────────────────────────

_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Return (and lazily create) the async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


# ── Cache helpers ─────────────────────────────────────────────

DEFAULT_TTL = 300  # 5 minutes for dashboard cache


async def cache_get(key: str) -> Any | None:
    client = await get_redis()
    raw = await client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    client = await get_redis()
    await client.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_delete(key: str) -> None:
    client = await get_redis()
    await client.delete(key)


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a glob pattern (e.g. 'dashboard:*')."""
    client = await get_redis()
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
