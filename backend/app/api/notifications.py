"""Notification API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import APIResponse
from app.core.security import get_current_user, TokenPayload
from app.db.session import get_db
from app.schemas.notifications import NotificationDetail, NotificationListResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


@router.get("", response_model=APIResponse)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    notification_type: str | None = Query(None, description="Filter by type"),
    is_read: bool | None = Query(None, description="Filter by read status"),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """List notifications for the current user with unread count."""
    items, total, unread_count = await NotificationService.list_notifications(
        db=db,
        user_id=int(user.sub),
        page=page,
        page_size=page_size,
        notification_type=notification_type,
        is_read=is_read,
    )
    total_pages = (total + page_size - 1) // page_size if total else 0

    return APIResponse.success(
        data=NotificationListResponse(
            items=items,
            total=total,
            unread_count=unread_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ).model_dump(),
    )


@router.post("/{notification_id}/read", response_model=APIResponse)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Mark a single notification as read."""
    notification = await NotificationService.mark_read(
        db, notification_id, user_id=int(user.sub)
    )
    return APIResponse.success(
        data=NotificationDetail.model_validate(notification).model_dump(),
        message="Notification marked as read",
    )


@router.post("/read-all", response_model=APIResponse)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Mark all notifications for the current user as read."""
    count = await NotificationService.mark_all_read(db, user_id=int(user.sub))
    return APIResponse.success(
        data={"marked_count": count},
        message=f"Marked {count} notifications as read",
    )
