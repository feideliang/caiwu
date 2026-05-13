"""Correlation endpoints: analyze, list, calibrate."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.core.response import APIResponse
from app.core.security import get_current_user, TokenPayload
from app.db.session import get_db
from app.models.v3 import CorrelationCalibration, CorrelationResult
from app.schemas.correlations import (
    CorrelationAnalyzeRequest,
    CorrelationCalibrateRequest,
)
from app.services.correlation import analyze_correlation, classify_strength, _mock_explanation
from app.services.audit_service import audit_action, log_audit

router = APIRouter(prefix="/correlations", tags=["correlations"])


@router.post("/analyze", response_model=APIResponse)
async def analyze_correlation_endpoint(
    body: CorrelationAnalyzeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Run correlation analysis between two financial metrics.

    Supports Pearson and Spearman methods. Optionally requests AI explanation.
    """
    result = await analyze_correlation(
        db=db,
        metric_a=body.metric_a,
        metric_b=body.metric_b,
        method=body.method,
        period_start=body.period_start,
        period_end=body.period_end,
        request_ai_explanation=body.request_ai_explanation,
    )

    # Audit log
    user_id = int(user.sub)
    trace_id = getattr(request.state, "trace_id", None)
    ip_address = request.client.host if request.client else None
    try:
        await log_audit(
            db=db,
            user_id=user_id,
            action="correlation_analyze",
            resource_type="correlation_result",
            resource_id=result.get("id"),
            after_value={"metric_a": body.metric_a, "metric_b": body.metric_b, "coefficient": result.get("coefficient")},
            ip_address=ip_address,
            trace_id=trace_id,
        )
    except Exception:
        pass

    # Rename metric_a/metric_b to variable_x/variable_y for response schema alignment
    result["variable_x"] = result.pop("metric_a")
    result["variable_y"] = result.pop("metric_b")

    return APIResponse.success(data=result)


@router.get("", response_model=APIResponse)
async def list_correlations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    """List all correlation analyses, most recent first."""
    stmt = select(CorrelationResult).order_by(CorrelationResult.computed_at.desc())

    count_stmt = select(func.count()).select_from(CorrelationResult)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = []
    calibration_stmt = select(CorrelationCalibration).where(
        CorrelationCalibration.correlation_id.in_([row.id for row in rows])
    ).order_by(CorrelationCalibration.calibrated_at.desc())
    calibration_result = await db.execute(calibration_stmt)
    calibration_map: dict[int, dict] = {}
    for cal in calibration_result.scalars().all():
        if cal.correlation_id in calibration_map:
            continue
        action = None
        if cal.notes:
            try:
                import json
                action = json.loads(cal.notes).get("action")
            except Exception:
                action = None
        calibration_map[cal.correlation_id] = {
            "calibration_status": action,
            "calibrated_by": cal.calibrated_by,
            "calibrated_at": cal.calibrated_at.isoformat() if cal.calibrated_at else None,
        }

    for row in rows:
        explanation = _mock_explanation(row.metric_a, row.metric_b, row.coefficient, row.p_value, classify_strength(row.coefficient))
        calibration = calibration_map.get(row.id, {})
        items.append({
            "id": row.id,
            "metric_a": row.metric_a,
            "metric_b": row.metric_b,
            "variable_x": row.metric_a,
            "variable_y": row.metric_b,
            "coefficient": row.coefficient,
            "correlation_coefficient": row.coefficient,
            "p_value": row.p_value,
            "sample_size": row.sample_size,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "strength": classify_strength(row.coefficient),
            "ai_explanation": explanation,
            "calibration_status": calibration.get("calibration_status"),
            "calibrated_by": calibration.get("calibrated_by"),
            "calibrated_at": calibration.get("calibrated_at"),
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
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


@router.post("/{correlation_id}/calibrate", response_model=APIResponse)
@audit_action(resource_type="correlation_calibration", action="calibrate_correlation", extract_resource_id=lambda kw, res: kw.get("correlation_id"))
async def calibrate_correlation(
    correlation_id: int,
    body: CorrelationCalibrateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Manual calibration: confirm / doubt / reject a correlation result.

    Creates a calibration record with the user's judgment.
    """
    # Verify correlation exists
    corr = await db.get(CorrelationResult, correlation_id)
    if corr is None:
        raise ResourceNotFoundError(f"Correlation result {correlation_id} not found")

    user_id = user.sub
    coefficient = body.calibrated_coefficient or corr.coefficient

    # Store calibration action in notes as JSON
    import json
    notes_json = json.dumps({"action": body.action, "user_notes": body.notes})

    calibration = CorrelationCalibration(
        correlation_id=correlation_id,
        calibrated_coefficient=coefficient,
        calibrated_by=user_id,
        notes=notes_json,
    )
    db.add(calibration)
    await db.flush()

    return APIResponse.success(
        data={
            "id": calibration.id,
            "correlation_id": correlation_id,
            "action": body.action,
            "calibrated_coefficient": coefficient,
            "calibrated_at": calibration.calibrated_at.isoformat() if calibration.calibrated_at else None,
        },
        message=f"Correlation {body.action}ed",
    )
