"""Data freshness service — determines sync status and caching."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set
from app.models.core import DataBatch, SyncJob, SyncStatus


# Status thresholds (in minutes)
_FRESH_THRESHOLD_MIN = 30
_STALE_THRESHOLD_MIN = 60

_CACHE_KEY = "system:data_freshness"
_CACHE_TTL = 60  # seconds


async def get_data_freshness(db: AsyncSession) -> dict:
    """Return data freshness status with 60s cache.

    Status logic:
    - fresh: last sync < 30 minutes ago
    - stale: last sync 30-60 minutes ago
    - error: last sync > 60 minutes ago or no sync history
    """
    cached = await cache_get(_CACHE_KEY)
    if cached is not None:
        return cached

    result = await _compute_freshness(db)
    await cache_set(_CACHE_KEY, result, _CACHE_TTL)
    return result


async def _compute_freshness(db: AsyncSession) -> dict:
    # Get latest successful sync job
    stmt = (
        select(SyncJob.finished_at, SyncJob.started_at)
        .where(SyncJob.status == SyncStatus.SUCCESS)
        .where(SyncJob.finished_at.isnot(None))
        .order_by(SyncJob.finished_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.first()

    last_sync_time: datetime | None = None
    if row:
        last_sync_time = row[0]

    # Also check latest batch
    batch_stmt = (
        select(DataBatch.processed_at)
        .where(DataBatch.status == SyncStatus.SUCCESS)
        .where(DataBatch.processed_at.isnot(None))
        .order_by(DataBatch.processed_at.desc())
        .limit(1)
    )
    batch_result = await db.execute(batch_stmt)
    batch_row = batch_result.first()
    if batch_row and batch_row[0]:
        if last_sync_time is None or batch_row[0] > last_sync_time:
            last_sync_time = batch_row[0]

    # Determine status
    if last_sync_time is None:
        status = "error"
    else:
        # Use UTC now for comparison
        now = datetime.now(timezone.utc)
        if last_sync_time.tzinfo is None:
            last_sync_time = last_sync_time.replace(tzinfo=timezone.utc)
        diff_minutes = (now - last_sync_time).total_seconds() / 60

        if diff_minutes < _FRESH_THRESHOLD_MIN:
            status = "fresh"
        elif diff_minutes < _STALE_THRESHOLD_MIN:
            status = "stale"
        else:
            status = "error"

    # Get data range (min/max period from agg_period_summary)
    from app.models.core import AggPeriodSummary

    range_stmt = select(
        func.min(AggPeriodSummary.period),
        func.max(AggPeriodSummary.period),
    )
    range_result = await db.execute(range_stmt)
    range_row = range_result.first()
    data_range = None
    if range_row and range_row[0]:
        data_range = {"start": range_row[0], "end": range_row[1]}

    # Compute next sync estimate
    next_sync_at = None
    if last_sync_time:
        from datetime import timedelta
        # Assume incremental sync every 4 hours
        next_sync_at = last_sync_time + timedelta(hours=4)

    return {
        "last_sync_time": last_sync_time.isoformat() if last_sync_time else None,
        "data_range": data_range,
        "status": status,
        "next_sync_at": next_sync_at.isoformat() if next_sync_at else None,
    }


async def invalidate_freshness_cache() -> None:
    """Clear the data freshness cache after a sync completes."""
    from app.core.cache import cache_delete

    await cache_delete(_CACHE_KEY)
