"""Notification service — manages user notifications."""

from __future__ import annotations

import logging
import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.models.v4 import Notification
from app.tasks.notification import create_notification_sync

logger = logging.getLogger(__name__)


VALID_NOTIFICATION_TYPES = {"report_completed", "report_failed", "data_sync", "system", "alert"}


class NotificationService:
    """Service for managing notifications."""

    @staticmethod
    async def list_notifications(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        notification_type: str | None = None,
        is_read: bool | None = None,
    ) -> tuple[list[dict], int, int]:
        """List notifications for a user. Returns (items, total, unread_count)."""

        base = select(Notification).where(Notification.user_id == user_id)

        if notification_type:
            base = base.where(Notification.notification_type == notification_type)
        if is_read is not None:
            base = base.where(Notification.is_read == is_read)

        # Unread count (independent of pagination filters)
        unread_stmt = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
        unread_result = await db.execute(unread_stmt)
        unread_count = unread_result.scalar_one()

        # Total count with filters
        base_ordered = base.order_by(Notification.created_at.desc())
        count_stmt = select(func.count()).select_from(base_ordered.subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        # Paginate
        stmt = base_ordered.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        notifications = result.scalars().all()

        items = [_to_dict(n) for n in notifications]
        return items, total, unread_count

    @staticmethod
    async def mark_read(db: AsyncSession, notification_id: int, user_id: int) -> Notification:
        """Mark a single notification as read."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        result = await db.execute(stmt)
        notification = result.scalar_one_or_none()
        if not notification:
            raise ResourceNotFoundError(f"Notification {notification_id} not found")

        notification.is_read = True
        await db.commit()
        await db.refresh(notification)
        return notification

    @staticmethod
    async def mark_all_read(db: AsyncSession, user_id: int) -> int:
        """Mark all notifications for a user as read. Returns count of updated rows."""
        from sqlalchemy import update

        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
            .values(is_read=True)
        )
        result = await db.execute(stmt)
        await db.commit()
        count = result.rowcount
        logger.info("Marked %d notifications as read for user %d", count, user_id)
        return count

    @staticmethod
    def send_notification_async(
        user_id: int,
        title: str,
        content: str | None = None,
        notification_type: str = "system",
        link: str | None = None,
        source_task_id: int | None = None,
    ) -> None:
        """Fire-and-forget notification creation via Celery."""
        if notification_type not in VALID_NOTIFICATION_TYPES:
            logger.warning("Unknown notification type: %s", notification_type)

        create_notification_sync(
            user_id=user_id,
            title=title,
            content=content,
            notification_type=notification_type,
            link=link,
            source_task_id=source_task_id,
        )


def _to_dict(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "user_id": notification.user_id,
        "title": notification.title,
        "content": notification.content,
        "notification_type": notification.notification_type,
        "is_read": notification.is_read,
        "link": notification.link,
        "source_task_id": notification.source_task_id,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }
