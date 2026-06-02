"""Celery task: sync dimension tables from wide table."""

from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_sync(table: str | None = None) -> dict:
    """Run dimension sync asynchronously."""
    import asyncpg
    from app.config import settings

    dsn = (
        f"postgresql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    )
    conn = await asyncpg.connect(dsn)

    try:
        from scripts.sync_dimensions import SYNC_TABLES

        tables_to_sync = {table: SYNC_TABLES[table]} if table else SYNC_TABLES
        results = {}

        for tbl, (upsert_sql, count_sql, display_name) in tables_to_sync.items():
            logger.info("Syncing %s...", display_name)
            await conn.execute(upsert_sql)
            count = await conn.fetchval(count_sql)
            results[tbl] = count
            logger.info("%s synced: %d records", display_name, count)

        return {"status": "ok", "counts": results}
    finally:
        await conn.close()


@celery_app.task(
    name="dim_sync.sync_all_dimensions",
    queue="data_sync",
    bind=True,
    acks_late=True,
    max_retries=2,
    default_retry_delay=30,
)
def sync_all_dimensions(self) -> dict:
    """Sync all dimension tables from income_margin_detail wide table."""
    logger.info("Starting dimension sync")
    try:
        result = asyncio.run(_run_sync())
        logger.info("Dimension sync complete: %s", result)
        return result
    except Exception as exc:
        logger.exception("Dimension sync failed")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise