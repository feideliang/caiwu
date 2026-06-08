"""Notification API endpoints — repurposed for Smart Insights delivery."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import APIResponse
from app.core.security import get_current_user, TokenPayload
from app.db.session import get_db
from app.models.v3 import Insight
from app.services.insight_rule_service import InsightRuleService
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


@router.get("", response_model=APIResponse)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    notification_type: str | None = Query(None, description="Filter by type (alias for insight_type)"),
    is_read: bool | None = Query(None, description="Filter by read status"),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Return Smart Insights (insight rules) as notifications."""
    metrics = await MetricsService.get_core_metrics(
        db=db, period=None, dimension="company",
        sections={"summary", "trend_series"},
    )
    customer_metrics = await MetricsService.get_core_metrics(
        db=db, period=None, dimension="customer",
        sections={"breakdowns"},
    )
    product_metrics = await MetricsService.get_core_metrics(
        db=db, period=None, dimension="product_bgbu",
        sections={"breakdowns"},
    )
    rule_items = await InsightRuleService.generate_insights(
        metrics,
        customer_breakdowns=customer_metrics.breakdowns,
        product_breakdowns=product_metrics.breakdowns,
    )

    # Hydrate status from DB
    if rule_items:
        stmt = select(Insight).where(Insight.generated_by == "rule")
        existing = (await db.execute(stmt)).scalars().all()
        status_lookup: dict[str, str] = {}
        for row in existing:
            meta = row.data_json or {}
            key = f"{meta.get('rule_code')}:{meta.get('period')}:{meta.get('dimension')}:{meta.get('dimension_value')}"
            if meta.get("__status"):
                status_lookup[key] = meta["__status"]
        for item in rule_items:
            meta = item.get("data_json") or {}
            key = f"{meta.get('rule_code')}:{meta.get('period')}:{meta.get('dimension')}:{meta.get('dimension_value')}"
            if key in status_lookup:
                item["status"] = status_lookup[key]

    # Map insight type to notification_type filter
    if notification_type:
        rule_items = [i for i in rule_items if i.get("type") == notification_type]
    if is_read is not None:
        target = "read" if is_read else "unread"
        rule_items = [i for i in rule_items if i.get("status") == target]

    total = len(rule_items)
    start = (page - 1) * page_size
    end = start + page_size
    paged = rule_items[start:end]
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    unread = len([i for i in rule_items if i.get("status") == "unread"])

    return APIResponse.success(
        data={
            "items": paged,
            "total": total,
            "unread_count": unread,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    )


@router.post("/{notification_id}/read", response_model=APIResponse)
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Mark a Smart Insight as read."""
    # Rule-generated insights have string IDs like 'rule:...'
    if not notification_id.startswith("rule:"):
        try:
            int_id = int(notification_id)
            stmt = select(Insight).where(Insight.id == int_id)
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                meta = row.data_json or {}
                meta["__status"] = "read"
                row.data_json = meta
                await db.flush()
        except (ValueError, TypeError):
            pass
    return APIResponse.success(data={"id": notification_id, "status": "read"})


@router.post("/read-all", response_model=APIResponse)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Mark all Smart Insights as read."""
    stmt = select(Insight).where(Insight.generated_by == "rule")
    result = await db.execute(stmt)
    rows = result.scalars().all()
    count = 0
    for row in rows:
        meta = row.data_json or {}
        meta["__status"] = "read"
        row.data_json = meta
        count += 1
    if count:
        await db.flush()
    return APIResponse.success(data={"marked_count": count})
