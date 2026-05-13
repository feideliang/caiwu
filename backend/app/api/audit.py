"""Audit log query endpoint — admin-only."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import APIResponse
from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.v4 import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=APIResponse)
async def list_audit_logs(
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    resource_id: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_role("admin")),
) -> APIResponse:
    """List audit logs with filtering. Admin-only.

    Returns: {code, message, data: {items, total, page, page_size, total_pages}, trace_id}
    """
    stmt = select(AuditLog)

    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= date_to)

    # Count
    count_stmt = select(func.count()).select_from(AuditLog)
    if user_id is not None:
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)
    if action:
        count_stmt = count_stmt.where(AuditLog.action == action)
    if resource_type:
        count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        count_stmt = count_stmt.where(AuditLog.resource_id == resource_id)
    if date_from:
        count_stmt = count_stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        count_stmt = count_stmt.where(AuditLog.created_at <= date_to)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = []
    for row in rows:
        items.append({
            "id": row.id,
            "user_id": row.user_id,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "detail": row.detail,
            "ip_address": row.ip_address,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })

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
