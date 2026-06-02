"""Celery task: sync rule config from DB to engine cache.

Triggered automatically when rules are created/updated via the API,
so the rule engine picks up threshold changes without manual seeding.
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


@celery_app.task(
    name="rule_sync.sync_rule_config",
    queue="default",
    bind=True,
    acks_late=True,
    max_retries=2,
    default_retry_delay=10,
)
def sync_rule_config(self, rule_code: str) -> dict:
    """Sync a single rule's config from DB to the engine cache (Redis).

    Reads the KnowledgeRule from DB by rule_code and writes its
    structured config (threshold, severity, condition, is_executable)
    to Redis for the rule engine to pick up.
    """
    logger.info("Syncing rule config for rule_code=%s", rule_code)

    session = _get_sync_db()
    try:
        from app.models.core import KnowledgeRule

        rule = session.query(KnowledgeRule).filter(
            KnowledgeRule.rule_code == rule_code,
            KnowledgeRule.is_active.is_(True),
        ).first()

        if not rule:
            logger.warning("No active rule found for rule_code=%s", rule_code)
            return {"rule_code": rule_code, "status": "not_found"}

        config = {
            "threshold": rule.threshold,
            "severity": rule.severity,
            "condition": rule.condition,
            "is_executable": rule.is_executable,
        }

        # Write to Redis directly via sync redis client
        import redis as sync_redis
        from app.config import settings

        r = sync_redis.from_url(settings.redis_url, decode_responses=True)
        redis_key = f"rule_config:{rule_code}"
        r.set(redis_key, json.dumps(config), ex=300)
        r.close()

        logger.info(
            "Rule config synced: %s -> threshold=%s, severity=%s",
            rule_code, rule.threshold, rule.severity,
        )

        return {"rule_code": rule_code, "status": "synced", "config": config}

    except Exception as exc:
        session.rollback()
        logger.exception("Failed to sync rule config for %s", rule_code)
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            raise self.retry(exc=exc, countdown=10 * (2 ** retry_count))
        raise
    finally:
        session.close()


@celery_app.task(
    name="rule_sync.sync_all_rule_configs",
    queue="default",
    bind=True,
    acks_late=True,
    max_retries=1,
    default_retry_delay=30,
)
def sync_all_rule_configs(self) -> dict:
    """Sync ALL executable rule configs from DB to Redis.

    Called on deployment or via admin to refresh the entire rule cache.
    """
    logger.info("Syncing all rule configs from DB to Redis")

    session = _get_sync_db()
    try:
        from app.models.core import KnowledgeRule

        rules = session.query(KnowledgeRule).filter(
            KnowledgeRule.rule_code.isnot(None),
            KnowledgeRule.is_active.is_(True),
        ).all()

        import redis as sync_redis
        from app.config import settings

        r = sync_redis.from_url(settings.redis_url, decode_responses=True)

        synced = 0
        for rule in rules:
            config = {
                "threshold": rule.threshold,
                "severity": rule.severity,
                "condition": rule.condition,
                "is_executable": rule.is_executable,
            }
            redis_key = f"rule_config:{rule.rule_code}"
            r.set(redis_key, json.dumps(config), ex=300)
            synced += 1

        r.close()

        logger.info("Synced %d rule configs to Redis", synced)
        return {"status": "ok", "synced_count": synced}

    except Exception as exc:
        session.rollback()
        logger.exception("Failed to sync all rule configs")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        raise
    finally:
        session.close()