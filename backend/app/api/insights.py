"""Insight endpoints: list, status update."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.core.response import APIResponse
from app.core.security import decode_access_token, TokenPayload, get_current_user
from app.db.session import get_db
from app.models.v3 import Insight
from app.schemas.insights import InsightStatusUpdate
from app.services.audit_service import audit_action
from app.services.insight_rule_service import InsightRuleService
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/insights", tags=["insights"])


def get_optional_user(request: Request) -> TokenPayload | None:
    """Try to extract JWT user from Authorization header; return None if not authenticated."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        return TokenPayload.model_validate(decode_access_token(auth_header.split(" ", 1)[1]))
    except Exception:
        return None


def _serialize_insight(row: Insight) -> dict:
    meta = row.data_json or {}
    status = meta.get("__status", "unread")
    severity = meta.get("severity", "medium")
    confidence = meta.get("confidence", 0.8)
    related_metric = meta.get("related_metric")
    related_chart_id = meta.get("related_chart_id")
    description = meta.get("description") or row.content

    # Strip internal keys already promoted to top-level
    clean_data = {k: v for k, v in meta.items() if not k.startswith("__")}

    return {
        "id": row.id,
        "type": row.insight_type or "anomaly",
        "title": row.title,
        "insight_type": row.insight_type,
        "description": description,
        "severity": severity,
        "confidence": confidence,
        "content": row.content,
        "status": status,
        "data_json": clean_data if clean_data else None,
        "related_metric": related_metric,
        "related_chart_id": related_chart_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": (row.updated_at.isoformat() if hasattr(row, "updated_at") and row.updated_at else None),
    }


@router.get("", response_model=APIResponse)
async def list_insights(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    insight_type: str | None = Query(None),
    status: str | None = Query(None),
    source: str | None = Query(None),
    period: str | None = Query(None),
    dimension: str = Query("company"),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_optional_user),
) -> APIResponse:
    """List insights with optional type and status filters."""
    if source == "rules":
        metrics = await MetricsService.get_core_metrics(
            db=db, period=period, dimension=dimension,
        )
        customer_metrics = await MetricsService.get_core_metrics(
            db=db, period=period, dimension="customer",
        )
        product_metrics = await MetricsService.get_core_metrics(
            db=db, period=period, dimension="product_line",
        )
        rule_items = await InsightRuleService.generate_insights(
            metrics,
            customer_breakdowns=customer_metrics.breakdowns,
            product_breakdowns=product_metrics.breakdowns,
        )

        # Hydrate status from DB by rule_code + period + dimension
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

        # Apply filters
        if insight_type:
            rule_items = [i for i in rule_items if i.get("type") == insight_type]
        if status:
            rule_items = [i for i in rule_items if i.get("status") == status]

        total = len(rule_items)
        start = (page - 1) * page_size
        end = start + page_size
        paged = rule_items[start:end]
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return APIResponse.success(data={
            "items": paged,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        })

    stmt = select(Insight)

    if insight_type:
        stmt = stmt.where(Insight.insight_type == insight_type)
    if status:
        # Status is stored in data_json.__status, default to 'unread' if NULL
        stmt = stmt.where(
            func.coalesce(Insight.data_json["__status"].as_string(), "unread") == status
        )

    # Count
    count_stmt = select(func.count()).select_from(Insight)
    if insight_type:
        count_stmt = count_stmt.where(Insight.insight_type == insight_type)
    if status:
        count_stmt = count_stmt.where(
            func.coalesce(Insight.data_json["__status"].as_string(), "unread") == status
        )

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Paginate
    stmt = stmt.order_by(Insight.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = []
    for row in rows:
        items.append(_serialize_insight(row))

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return APIResponse.success(
        data={
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    )


@router.get("/{insight_id}", response_model=APIResponse)
async def get_insight(
    insight_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_optional_user),
) -> APIResponse:
    """Get a single insight by ID."""
    stmt = select(Insight).where(Insight.id == insight_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError(f"Insight {insight_id} not found")

    return APIResponse.success(data=_serialize_insight(row))


@router.post("/{insight_id}/status", response_model=APIResponse)
@audit_action(resource_type="insight", action="update_insight_status", extract_resource_id=lambda kw, res: kw.get("insight_id"))
async def update_insight_status(
    insight_id: str,
    body: InsightStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    """Update insight status: read / process / ignore.

    Status is stored in the data_json column under '__status' key.
    Rule-generated insights (string IDs like 'rule:...') are ephemeral and
    don't need DB persistence — return success immediately.
    """
    # Rule-generated insights have string IDs — no DB row to update
    try:
        int_id = int(insight_id)
    except (ValueError, TypeError):
        return APIResponse.success(data={"id": insight_id, "status": body.status})

    row = await db.get(Insight, int_id)
    if row is None:
        raise ResourceNotFoundError(f"Insight {insight_id} not found")

    # Use dict copy to ensure SQLAlchemy detects the change (JSONB mutation tracking)
    new_data = dict(row.data_json or {})
    new_data["__status"] = body.status
    row.data_json = new_data

    await db.commit()

    return APIResponse.success(data={"id": insight_id, "status": body.status})
