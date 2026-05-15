"""Filter endpoints: dynamic filter options and filter-views CRUD.

Paths per spec:
  POST /api/v1/filter-options
  GET  /api/v1/filter-views
  POST /api/v1/filter-views
  DELETE /api/v1/filter-views/{id}
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.core.response import APIResponse
from app.core.security import get_current_user, TokenPayload
from app.db.session import get_db
from app.models.core import FinancialData
from app.models.v3 import FilterView
from app.schemas.filters import (
    FilterCondition,
    FilterViewCreate,
)
from app.services.audit_service import audit_action

router = APIRouter(prefix="", tags=["filter"])


def _normalize_view_filters(filters: dict | None) -> tuple[list[dict], str]:
    if not filters:
        return [], "AND"
    if "conditions" in filters:
        return list(filters.get("conditions") or []), str(filters.get("logic") or "AND")
    conditions = [
        {"field": key, "operator": value.get("operator", "eq"), "value": value.get("value")}
        for key, value in filters.items()
        if isinstance(value, dict)
    ]
    return conditions, "AND"


@router.get("/filter-options", response_model=APIResponse)
async def get_filter_options(
    dimension: str | None = Query(None, description="Dimension: period / entity / metric_name / department / product / product_line"),
    prefix: str | None = Query(None, description="Optional prefix filter"),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Return dynamic filter options for a given dimension.

    Supported dimensions: period, entity, metric_name, department, product, product_line.
    Queries the financial_data table for distinct values.
    """
    col_map = {
        "period": FinancialData.period,
        "entity": FinancialData.entity,
        "metric_name": FinancialData.metric_name,
    }

    if dimension:
        # Direct column dimensions
        if dimension in col_map:
            col = col_map[dimension]
            stmt = select(col).distinct().order_by(col)
            if prefix:
                stmt = stmt.where(col.like(f"{prefix}%"))
            result = await db.execute(stmt)
            options = [str(r[0]) for r in result.all() if r[0] is not None]
            return APIResponse.success(data={"dimension": dimension, "options": options, "total": len(options)})

        # Tag-based dimensions: department, product, product_line
        if dimension in ("department", "product", "product_line"):
            tag_key_map = {
                "department": ["department"],
                "product_line": ["product_line"],
                "product": ["product", "series"],
            }
            keys = tag_key_map.get(dimension, [])
            values = set()

            # Use raw SQL tags->>'key' for distinct extraction (SQLAlchemy JSON column quirks)
            from sqlalchemy import text
            for key in keys:
                sql = text(
                    f"SELECT DISTINCT tags->>'{key}' FROM financial_data "
                    f"WHERE tags IS NOT NULL AND tags->>'{key}' IS NOT NULL"
                )
                result = await db.execute(sql)
                for row in result:
                    val = row[0]
                    if val:
                        values.add(str(val))

            # For department, use tags->>'department' only (entity column contains garbled product names)
            # _extract_dimension falls back to entity, but filter options should be clean
            if dimension == "department":
                pass  # already collected from tags above

            options = sorted(values)
            if prefix:
                options = [o for o in options if o.startswith(prefix)]
            return APIResponse.success(data={"dimension": dimension, "options": options, "total": len(options)})

        # Unknown dimension
        return APIResponse.success(data={"dimension": dimension, "options": [], "total": 0})

    fields = [
        {"field": "period", "label": "期间", "type": "select", "options": []},
        {"field": "entity", "label": "主体", "type": "select", "options": []},
        {"field": "metric_name", "label": "指标", "type": "select", "options": []},
    ]
    recent_stmt = (
        select(FilterView)
        .where(FilterView.user_id == int(user.sub))
        .order_by(FilterView.created_at.desc())
        .limit(5)
    )
    recent_result = await db.execute(recent_stmt)
    recent_views = [
        {
            "id": v.id,
            "name": v.name,
            "dashboard_id": v.dashboard_id,
            "conditions": _normalize_view_filters(v.filters)[0],
            "logic": _normalize_view_filters(v.filters)[1],
            "created_by": v.user_id,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in recent_result.scalars().all()
    ]

    return APIResponse.success(data={"fields": fields, "recent_views": recent_views})


@router.get("/filter-views", response_model=APIResponse)
async def list_filter_views(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """List saved filter views for the current user (plus public ones)."""
    user_id = int(user.sub)

    stmt = (
        select(FilterView)
        .where((FilterView.user_id == user_id) | (FilterView.is_public == True))
        .order_by(FilterView.created_at.desc())
    )

    count_stmt = (
        select(func.count())
        .select_from(FilterView)
        .where((FilterView.user_id == user_id) | (FilterView.is_public == True))
    )

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = [
        {
            "id": r.id,
            "name": r.name,
            "dashboard_id": r.dashboard_id,
            "filters": r.filters,
            "conditions": _normalize_view_filters(r.filters)[0],
            "logic": _normalize_view_filters(r.filters)[1],
            "is_public": r.is_public,
            "created_by": r.user_id,
            "user_id": r.user_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

    return APIResponse.success(
        data={"items": items, "total": total, "page": page, "page_size": page_size}
    )


@router.post("/filter-views", response_model=APIResponse)
@audit_action(resource_type="filter_view", action="create_filter_view", extract_resource_id=lambda kw, res: res.data.get("id") if hasattr(res, "data") else None)
async def create_filter_view(
    body: FilterViewCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Create a saved filter view."""
    user_id = int(user.sub)

    payload = body.filters
    if payload is None:
        payload = {
            "conditions": [c.model_dump() for c in (body.conditions or [])],
            "logic": body.logic or "AND",
        }

    view = FilterView(
        name=body.name,
        user_id=user_id,
        dashboard_id=body.dashboard_id,
        filters=payload,
        is_public=body.is_public,
    )
    db.add(view)
    await db.flush()

    return APIResponse.success(
        data={
            "id": view.id,
            "name": view.name,
            "dashboard_id": view.dashboard_id,
            "filters": view.filters,
            "conditions": _normalize_view_filters(view.filters)[0],
            "logic": _normalize_view_filters(view.filters)[1],
            "is_public": view.is_public,
            "created_by": view.user_id,
            "user_id": view.user_id,
            "created_at": view.created_at.isoformat() if view.created_at else None,
        },
        message="Filter view created",
    )


@router.delete("/filter-views/{view_id}", response_model=APIResponse)
@audit_action(resource_type="filter_view", action="delete_filter_view", extract_resource_id=lambda kw, res: kw.get("view_id"))
async def delete_filter_view(
    view_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Delete a saved filter view. Only the owner can delete."""
    user_id = int(user.sub)

    view = await db.get(FilterView, view_id)
    if view is None:
        raise ResourceNotFoundError(f"Filter view {view_id} not found")

    if view.user_id != user_id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("You can only delete your own filter views")

    await db.delete(view)
    await db.flush()

    return APIResponse.success(message="Filter view deleted")
