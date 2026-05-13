"""Data quality API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import APIResponse
from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.core import DataQualityLog

router = APIRouter(prefix="/data-quality", tags=["data-quality"])


@router.get("/summary", response_model=APIResponse)
async def get_quality_summary(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_role("admin", "analyst")),
) -> APIResponse:
    stmt = select(DataQualityLog.status, func.count().label("cnt"))
    stmt = stmt.group_by(DataQualityLog.status)
    result = await db.execute(stmt)
    counts = {r.status: r.cnt for r in result.all()}

    total = sum(counts.values()) or 1
    passed = counts.get("PASSED", 0)
    warnings = counts.get("WARNING", 0)
    failed = counts.get("FAILED", 0)

    rule_stmt = select(DataQualityLog.rule_name, DataQualityLog.status, func.count().label("cnt"))
    rule_stmt = rule_stmt.group_by(DataQualityLog.rule_name, DataQualityLog.status)
    rule_result = await db.execute(rule_stmt)
    by_rule = [{"rule_name": r.rule_name, "status": r.status, "count": r.cnt} for r in rule_result.all()]

    return APIResponse.success(data={
        "total_checks": total,
        "passed": passed,
        "warnings": warnings,
        "failed": failed,
        "pass_rate": round(passed / total, 4),
        "by_rule": by_rule,
    })


@router.get("/errors", response_model=APIResponse)
async def get_quality_errors(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_role("admin", "analyst")),
) -> APIResponse:
    stmt = select(DataQualityLog)
    if status:
        stmt = stmt.where(DataQualityLog.status == status)
    stmt = stmt.order_by(DataQualityLog.created_at.desc())

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = [
        {"id": r.id, "batch_id": r.batch_id, "rule_name": r.rule_name,
         "status": r.status, "message": r.message, "created_at": str(r.created_at) if r.created_at else None}
        for r in result.scalars().all()
    ]
    return APIResponse.success(data={"items": items, "total": total, "page": page, "page_size": page_size})
