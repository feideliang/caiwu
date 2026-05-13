"""Core metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import APIResponse
from app.core.security import TokenPayload, get_current_user
from app.db.session import get_db
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/core", response_model=APIResponse)
async def get_core_metrics(
    period: str | None = Query(None),
    dimension: str = Query("company"),
    entity: str | None = Query(None),
    compare: str = Query("all"),
    high_margin_threshold: float = Query(40.0),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    result = await MetricsService.get_core_metrics(
        db=db,
        period=period,
        dimension=dimension,
        entity=entity,
        compare=compare,
        high_margin_threshold=high_margin_threshold,
    )
    return APIResponse.success(data=result.model_dump())
