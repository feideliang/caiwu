"""Transaction analysis API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import APIResponse
from app.core.security import TokenPayload, get_current_user
from app.db.session import get_db
from app.schemas.transactions import TransactionQueryParams
from app.services.transaction_service import transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/contracts", response_model=APIResponse)
async def get_contracts(
    period: str | None = Query(None),
    entity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    effective_entity = entity
    if user.role != "admin" and user.department:
        effective_entity = user.department
    items, total = await transaction_service.get_contracts(db, period, effective_entity, page, page_size)
    return APIResponse.success(data={"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/orders", response_model=APIResponse)
async def get_orders(
    period_from: str | None = Query(None),
    period_to: str | None = Query(None),
    min_value: float | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    dept = user.department if (user.role != "admin" and user.department) else None
    items, total = await transaction_service.get_orders(db, period_from, period_to, min_value, page, page_size, department=dept)
    return APIResponse.success(data={"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/projects", response_model=APIResponse)
async def get_projects(
    entity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    effective_entity = entity
    if user.role != "admin" and user.department:
        effective_entity = user.department
    items, total = await transaction_service.get_projects(db, effective_entity, page, page_size)
    return APIResponse.success(data={"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/anomalies", response_model=APIResponse)
async def get_anomalies(
    threshold: float = Query(2.0, ge=0),
    metric_names: str | None = Query(None),
    period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    dept = user.department if (user.role != "admin" and user.department) else None
    items = await transaction_service.detect_anomalies(db, threshold, metric_names, period, department=dept)
    return APIResponse.success(data=items)


@router.get("/large-amounts", response_model=APIResponse)
async def get_large_amounts(
    threshold: float = Query(1000000, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    dept = user.department if (user.role != "admin" and user.department) else None
    items, total = await transaction_service.get_large_amounts(db, threshold, page, page_size, department=dept)
    return APIResponse.success(data={"items": items, "total": total, "page": page, "page_size": page_size})
