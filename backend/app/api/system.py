"""System endpoints: data freshness status."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import APIResponse
from app.core.security import get_current_user
from app.db.session import get_db
from app.services.freshness import get_data_freshness

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/data-freshness", response_model=APIResponse)
async def data_freshness(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    """Return data freshness status.

    Returns:
    - last_sync_time: timestamp of the last successful sync
    - data_range: {start, end} period range covered by the data
    - status: fresh (<30min) / stale (30-60min) / error (>60min)
    - next_sync_at: estimated next sync time

    Cached with 60s TTL.
    """
    result = await get_data_freshness(db)
    return APIResponse.success(data=result)
