"""Report generation API endpoints."""

from __future__ import annotations

import logging
import math
import os

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, ReportGenerationFailedError
from app.core.response import APIResponse, ErrorCode
from app.core.security import get_current_user, TokenPayload
from app.db.session import get_db
from app.schemas.reports import ReportCreateRequest, ReportDetail, ReportListResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])
logger = logging.getLogger(__name__)


@router.post("", response_model=APIResponse, status_code=201)
async def create_report(
    body: ReportCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Create a new report generation task.

    Returns immediately with status 'pending'; the task runs asynchronously.
    """
    try:
        report = await ReportService.create_report(
            db=db,
            user_id=int(user.sub),
            report_type=body.report_type,
            period=body.period,
            output_format=body.output_format,
            params=body.params,
            parent_task_id=body.parent_task_id,
        )
        return APIResponse.success(
            data=ReportDetail.model_validate(report).model_dump(),
            message="Report generation task created",
        )
    except Exception as exc:
        logger.exception("Failed to create report")
        return APIResponse.error(
            code=ErrorCode.REPORT_GENERATION_FAILED,
            message=str(exc),
        )


@router.get("", response_model=APIResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="Filter by status"),
    report_type: str | None = Query(None, description="Filter by report type"),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """List reports for the current user with optional filters."""
    items, total = await ReportService.list_reports(
        db=db,
        user_id=int(user.sub),
        page=page,
        page_size=page_size,
        status=status,
        report_type=report_type,
    )
    total_pages = math.ceil(total / page_size) if total else 0

    return APIResponse.success(
        data=ReportListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ).model_dump(),
    )


@router.get("/{report_id}", response_model=APIResponse)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Get detail for a single report task."""
    report = await ReportService.get_report(db, report_id, user_id=int(user.sub))
    return APIResponse.success(data=ReportDetail.model_validate(report).model_dump())


@router.post("/{report_id}/cancel", response_model=APIResponse)
async def cancel_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Cancel a running report generation task."""
    try:
        report = await ReportService.cancel_report(db, report_id, user_id=int(user.sub))
        return APIResponse.success(
            data=ReportDetail.model_validate(report).model_dump(),
            message="Report task cancelled",
        )
    except BusinessError as exc:
        return APIResponse.error(code=exc.code, message=str(exc))


@router.post("/{report_id}/retry", response_model=APIResponse)
async def retry_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Retry a failed report task (creates a new child task)."""
    try:
        report = await ReportService.retry_report(db, report_id, user_id=int(user.sub))
        return APIResponse.success(
            data=ReportDetail.model_validate(report).model_dump(),
            message="Report task retried",
        )
    except (BusinessError, ReportGenerationFailedError) as exc:
        return APIResponse.error(code=exc.code, message=str(exc))


@router.get("/{report_id}/download")
async def download_report(
    report_id: int,
    token: str | None = Query(None),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Download the generated report file.

    Accepts JWT token via query parameter (for browser downloads) or Authorization header.
    """
    from app.core.security import decode_access_token, TokenPayload

    # Try token from query param first, then Authorization header
    user: TokenPayload | None = None
    if token:
        try:
            user = TokenPayload.model_validate(decode_access_token(token))
        except Exception:
            pass

    if user is None:
        auth_header = request.headers.get("Authorization") if request else None
        if auth_header and auth_header.startswith("Bearer "):
            try:
                user = TokenPayload.model_validate(decode_access_token(auth_header.split(" ", 1)[1]))
            except Exception:
                pass

    if user is None:
        from app.core.exceptions import AuthenticationError
        raise AuthenticationError("Authentication required")

    report = await ReportService.get_report(db, report_id, user_id=int(user.sub))

    file_info = ReportService.get_file_path(report)
    if not file_info:
        return APIResponse.error(
            code=ErrorCode.NOT_FOUND,
            message="Report file not available (task not completed or file missing)",
        )

    file_path, file_name = file_info

    if not os.path.exists(file_path):
        return APIResponse.error(
            code=ErrorCode.NOT_FOUND,
            message="Report file has been deleted or moved",
        )

    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type="application/octet-stream",
    )
