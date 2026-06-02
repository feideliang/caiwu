"""Dynamic rule config — reads executable rule settings from DB/Redis.

Provides a single source of truth for thresholds used by the rule engine.
Flow:  Redis cache → DB → hardcoded fallback.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis

logger = logging.getLogger(__name__)

# ── Cache key ──────────────────────────────────────────────────

_RULE_CONFIG_PREFIX = "rule_config:"

# ── Hardcoded fallbacks ──────────────────────────────────────

_FALLBACK_RULES: dict[str, dict[str, Any]] = {
    "GROSS_MARGIN_SEVERE_LOW": {"threshold": 10, "severity": "high", "condition": "gm < 10", "is_executable": True},
    "GROSS_MARGIN_LOW": {"threshold": 20, "severity": "medium", "condition": "gm < 20", "is_executable": True},
    "GROSS_MARGIN_HIGH": {"threshold": 60, "severity": "medium", "condition": "gm > 60", "is_executable": True},
    "REVENUE_TREND_UP": {"threshold": 0, "severity": "low", "condition": "revenue_mom > 0 for 3 periods", "is_executable": True},
    "GROSS_PROFIT_TREND_UP": {"threshold": 0, "severity": "low", "condition": "gp_mom > 0 for 3 periods", "is_executable": True},
    "CUSTOMER_CONCENTRATION": {"threshold": 10, "severity": "high", "condition": "share > 10", "is_executable": True},
    "CUSTOMER_CONCENTRATION_TOP3": {"threshold": 60, "severity": "high", "condition": "top3 > 60", "is_executable": True},
    "PRODUCT_CONCENTRATION": {"threshold": 40, "severity": "high", "condition": "share > 40", "is_executable": True},
    "PRODUCT_CONCENTRATION_TOP3": {"threshold": 70, "severity": "high", "condition": "top3 > 70", "is_executable": True},
}


def _build_rule_key(rule_code: str) -> str:
    return f"{_RULE_CONFIG_PREFIX}{rule_code}"


async def get_rule_config(rule_code: str, db: AsyncSession | None = None) -> dict[str, Any] | None:
    """Read rule config: Redis → DB → hardcoded fallback.

    Returns dict with keys: threshold, severity, condition, is_executable.
    Returns None only if no rule exists anywhere for this code.
    """
    # 1. Try Redis
    redis_key = _build_rule_key(rule_code)
    try:
        client = await get_redis()
        raw = await client.get(redis_key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.warning("Redis read failed for rule %s: %s", rule_code, exc)

    # 2. Try DB
    if db is not None:
        try:
            from app.models.core import KnowledgeRule  # avoid circular import

            stmt = select(KnowledgeRule).where(KnowledgeRule.rule_code == rule_code, KnowledgeRule.is_active.is_(True))
            result = await db.execute(stmt)
            rule = result.scalar_one_or_none()
            if rule:
                config = _rule_to_config(rule)
                # write back to Redis
                try:
                    await client.set(redis_key, json.dumps(config), ex=300)
                except Exception:
                    pass
                return config
        except Exception as exc:
            logger.warning("DB read failed for rule %s: %s", rule_code, exc)

    # 3. Hardcoded fallback
    return _FALLBACK_RULES.get(rule_code)


def _rule_to_config(rule: Any) -> dict[str, Any]:
    """Convert a KnowledgeRule ORM object to a config dict."""
    return {
        "threshold": rule.threshold,
        "severity": rule.severity,
        "condition": rule.condition,
        "is_executable": rule.is_executable,
    }


async def set_rule_config(rule_code: str, config: dict[str, Any], ttl: int = 300) -> None:
    """Write rule config to Redis cache."""
    redis_key = _build_rule_key(rule_code)
    try:
        client = await get_redis()
        await client.set(redis_key, json.dumps(config), ex=ttl)
    except Exception as exc:
        logger.warning("Redis write failed for rule %s: %s", rule_code, exc)


async def invalidate_rule_config(rule_code: str) -> None:
    """Remove rule config from Redis cache."""
    redis_key = _build_rule_key(rule_code)
    try:
        client = await get_redis()
        await client.delete(redis_key)
    except Exception as exc:
        logger.warning("Redis delete failed for rule %s: %s", rule_code, exc)


async def invalidate_all_rule_configs() -> None:
    """Remove all rule configs from Redis cache."""
    from app.core.cache import cache_delete_pattern

    await cache_delete_pattern(f"{_RULE_CONFIG_PREFIX}*")


def format_threshold_description(rule_code: str, threshold: float | None = None) -> str:
    """Return a human-readable description of a rule's threshold condition."""
    descriptions = {
        "GROSS_MARGIN_SEVERE_LOW": lambda t: f"低于 {t:.0f}% 阈值" if t else "低于 10% 阈值",
        "GROSS_MARGIN_LOW": lambda t: f"低于 {t:.0f}% 阈值" if t else "低于 20% 阈值",
        "GROSS_MARGIN_HIGH": lambda t: f"高于 {t:.0f}%" if t else "高于 60%",
        "CUSTOMER_CONCENTRATION": lambda t: f"超过 {t:.0f}% 阈值" if t else "超过 10% 阈值",
        "CUSTOMER_CONCENTRATION_TOP3": lambda t: f"超过 {t:.0f}%" if t else "超过 60%",
        "PRODUCT_CONCENTRATION": lambda t: f"超过 {t:.0f}% 阈值" if t else "超过 40% 阈值",
        "PRODUCT_CONCENTRATION_TOP3": lambda t: f"超过 {t:.0f}%" if t else "超过 70%",
    }
    formatter = descriptions.get(rule_code)
    if formatter:
        return formatter(threshold)
    return f"阈值 {threshold}" if threshold is not None else ""