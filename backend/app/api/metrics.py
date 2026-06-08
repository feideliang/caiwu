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
    period_dimension: str = Query("monthly"),
    compare_period: str | None = Query(None),
    period_start: str | None = Query(None),
    period_end: str | None = Query(None),
    high_margin_threshold: float = Query(40.0),
    product: str | None = Query(None),
    department: str | None = Query(None),
    customer: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    # Determine bgbu_filter from user.department or explicit department param
    bgbu_filter = "ALL"
    if user.role != "admin" and user.department:
        bgbu_filter = user.department
    elif department:
        bgbu_filter = department

    # Map generic entity to dimension-specific param
    if entity:
        if dimension == 'customer' and not customer:
            customer = entity
        elif dimension == 'sales_product':
            # sales_product drill-down: entity is always a product filter
            # (either product_bgbu name from ProductAnalysisPage, or product model from frontend drill)
            if not product:
                product = entity
        elif dimension == 'product_bgbu' and not product:
            product = entity
        elif dimension == 'department' and not department:
            department = entity

    result = await MetricsService.get_core_metrics(
        db=db,
        period=period,
        dimension=dimension,
        entity=entity,
        compare=compare,
        period_dimension=period_dimension,
        compare_period=compare_period,
        period_start=period_start,
        period_end=period_end,
        high_margin_threshold=high_margin_threshold,
        product=product,
        customer=customer,
        bgbu_filter=bgbu_filter,
    )
    return APIResponse.success(data=result.model_dump())
