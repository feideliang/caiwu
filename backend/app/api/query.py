"""Query DSL endpoint — generic table querying with filters, sort, pagination."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.core.response import APIResponse
from app.core.security import get_current_user
from app.db.session import get_db
from app.schemas.query import QueryRequest, QueryResponse
from app.models.core import (
    DataBatch,
    DataSource,
    DataQualityLog,
    ChartConfig,
    DashboardLayout,
    UserPreference,
    SystemConfig,
    SyncJob,
)
from app.models.v3 import (
    Insight,
    FilterView,
    CorrelationResult,
    CorrelationCalibration,
    PredictionResult,
    ReportTask,
)
from app.models.v4 import AuditLog, Notification, User, Role

router = APIRouter(prefix="/query", tags=["query"])

_TABLE_MAP: dict[str, type] = {
    "data_batch": DataBatch,
    "data_source": DataSource,
    "data_quality_log": DataQualityLog,
    "chart_config": ChartConfig,
    "dashboard_layout": DashboardLayout,
    "user_preference": UserPreference,
    "system_config": SystemConfig,
    "sync_job": SyncJob,
    "insight": Insight,
    "filter_view": FilterView,
    "correlation_result": CorrelationResult,
    "correlation_calibration": CorrelationCalibration,
    "prediction_result": PredictionResult,
    "report_task": ReportTask,
    "audit_log": AuditLog,
    "notification": Notification,
    "users": User,
    "roles": Role,
}

_READ_ONLY_TABLES = {
    "data_batch", "data_quality_log", "insight",
    "correlation_result", "correlation_calibration", "prediction_result",
}


@router.post("", response_model=APIResponse)
async def execute_query(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    _user = Depends(get_current_user),
) -> APIResponse:
    """Execute a structured query against a named logical table."""
    model = _TABLE_MAP.get(body.table)
    if model is None:
        raise ResourceNotFoundError(f"Unknown table: {body.table}")

    stmt = select(model)

    # Apply field selection
    if body.fields:
        cols = [getattr(model, f) for f in body.fields if hasattr(model, f)]
        if cols:
            stmt = select(*cols).select_from(model)

    # Apply filters
    for f in body.filters:
        if not hasattr(model, f.field):
            continue
        col = getattr(model, f.field)
        op = f.operator
        val = f.value
        if op == "eq":
            stmt = stmt.where(col == val)
        elif op == "ne":
            stmt = stmt.where(col != val)
        elif op == "gt":
            stmt = stmt.where(col > val)
        elif op == "gte":
            stmt = stmt.where(col >= val)
        elif op == "lt":
            stmt = stmt.where(col < val)
        elif op == "lte":
            stmt = stmt.where(col <= val)
        elif op == "in":
            stmt = stmt.where(col.in_(val))
        elif op == "like":
            stmt = stmt.where(col.like(f"%{val}%"))

    # Apply sort
    from sqlalchemy import desc

    for s in body.sort:
        if hasattr(model, s.field):
            col = getattr(model, s.field)
            stmt = stmt.order_by(desc(col) if s.order == "desc" else col)

    # Count
    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(model)
    # Re-apply filters to count
    for f in body.filters:
        if not hasattr(model, f.field):
            continue
        col = getattr(model, f.field)
        op = f.operator
        val = f.value
        if op == "eq":
            count_stmt = count_stmt.where(col == val)
        elif op == "ne":
            count_stmt = count_stmt.where(col != val)
        elif op == "gt":
            count_stmt = count_stmt.where(col > val)
        elif op == "gte":
            count_stmt = count_stmt.where(col >= val)
        elif op == "lt":
            count_stmt = count_stmt.where(col < val)
        elif op == "lte":
            count_stmt = count_stmt.where(col <= val)
        elif op == "in":
            count_stmt = count_stmt.where(col.in_(val))
        elif op == "like":
            count_stmt = count_stmt.where(col.like(f"%{val}%"))

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Paginate
    stmt = stmt.offset((body.page - 1) * body.page_size).limit(body.page_size)
    result = await db.execute(stmt)

    rows = [dict(r._mapping) for r in result.mappings().all()]

    return APIResponse.success(
        data=QueryResponse(
            rows=rows,
            total=total,
            page=body.page,
            page_size=body.page_size,
        ).model_dump()
    )
