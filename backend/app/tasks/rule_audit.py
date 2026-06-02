"""Celery task: periodic audit of all rules against engine implementation.

Compares DB-stored rule definitions against the currently active
engine config (Redis cache / hardcoded fallbacks) and logs
any inconsistencies.
"""

from __future__ import annotations

import json
import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_sync_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.config import settings

    engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine)()


# ── Hardcoded fallback reference for comparison ───────────────

_FALLBACK_RULES: dict[str, dict] = {
    "GROSS_MARGIN_SEVERE_LOW": {"threshold": 10, "severity": "high"},
    "GROSS_MARGIN_LOW": {"threshold": 20, "severity": "medium"},
    "GROSS_MARGIN_HIGH": {"threshold": 60, "severity": "medium"},
    "CUSTOMER_CONCENTRATION": {"threshold": 10, "severity": "high"},
    "CUSTOMER_CONCENTRATION_TOP3": {"threshold": 60, "severity": "high"},
    "PRODUCT_CONCENTRATION": {"threshold": 40, "severity": "high"},
    "PRODUCT_CONCENTRATION_TOP3": {"threshold": 70, "severity": "high"},
}


def _get_redis():
    import redis as sync_redis
    from app.config import settings

    return sync_redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(
    name="rule_audit.audit_all_rules",
    queue="default",
    bind=True,
    acks_late=True,
    max_retries=1,
    default_retry_delay=30,
)
def audit_all_rules(self) -> dict:
    """Audit all rules: compare DB + Redis + hardcoded fallback consistency.

    Finds and logs:
    - Rules with rule_code that differ between DB and Redis cache
    - Executable rules missing from Redis (cache miss)
    - DB rules whose threshold/severity don't match hardcoded fallback

    Returns a report dict with mismatches and warnings.
    """
    logger.info("Starting audit of all rules against engine implementation")

    session = _get_sync_db()
    r = _get_redis()
    mismatches: list[dict] = []
    cache_misses: list[str] = []

    try:
        from app.models.core import KnowledgeRule

        db_rules = session.query(KnowledgeRule).filter(
            KnowledgeRule.rule_code.isnot(None),
            KnowledgeRule.is_active.is_(True),
        ).all()

        for rule in db_rules:
            code = rule.rule_code
            redis_key = f"rule_config:{code}"

            # Read from Redis
            raw = r.get(redis_key)
            redis_cfg = json.loads(raw) if raw else None

            if not redis_cfg:
                cache_misses.append(code)
                # Try to compare DB vs fallback directly
                fb = _FALLBACK_RULES.get(code)
                if fb:
                    db_config = {
                        "threshold": rule.threshold,
                        "severity": rule.severity,
                    }
                    db_vs_fb = _compare_configs(db_config, fb)
                    if db_vs_fb:
                        mismatches.append({
                            "rule_code": code,
                            "type": "db_vs_fallback",
                            "db": db_config,
                            "fallback": fb,
                            "diff": db_vs_fb,
                        })
                continue

            # Compare DB vs Redis
            db_config = {
                "threshold": rule.threshold,
                "severity": rule.severity,
                "condition": rule.condition,
            }
            redis_compare = {
                "threshold": redis_cfg.get("threshold"),
                "severity": redis_cfg.get("severity"),
                "condition": redis_cfg.get("condition"),
            }
            diff = _compare_configs(db_config, redis_compare)
            if diff:
                mismatches.append({
                    "rule_code": code,
                    "type": "db_vs_redis",
                    "db": db_config,
                    "redis": redis_compare,
                    "diff": diff,
                })

        # Also check for formula-type (non-executable) rules
        formula_rules = session.query(KnowledgeRule).filter(
            KnowledgeRule.is_executable.is_(False),
            KnowledgeRule.rule_code.is_(None),
        ).all()
        formula_count = len(formula_rules)

        report = {
            "total_db_rules_with_code": len(db_rules),
            "non_executable_formula_rules": formula_count,
            "cache_misses": cache_misses,
            "mismatches": mismatches,
            "mismatch_count": len(mismatches),
        }

        if mismatches:
            logger.warning(
                "Rule audit found %d mismatches, %d cache misses. Report: %s",
                len(mismatches), len(cache_misses), json.dumps(report, default=str),
            )
            for m in mismatches:
                logger.warning(
                    "Mismatch: rule_code=%s type=%s diff=%s",
                    m["rule_code"], m["type"], m["diff"],
                )
        else:
            logger.info("Rule audit passed: all %d rules consistent", len(db_rules))

        return report

    except Exception as exc:
        logger.exception("Rule audit failed")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        return {"status": "error", "error": str(exc)}
    finally:
        session.close()
        r.close()


def _compare_configs(a: dict, b: dict) -> list[str]:
    """Return list of field names that differ between two config dicts.

    Treats None and missing keys as equal.
    """
    diffs = []
    all_keys = set(a.keys()) | set(b.keys())
    for k in sorted(all_keys):
        va = a.get(k)
        vb = b.get(k)
        if va is None and vb is None:
            continue
        if va != vb:
            diffs.append(f"{k}: {va} vs {vb}")
    return diffs