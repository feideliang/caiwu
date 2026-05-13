"""Celery task helpers for creating notifications."""

from __future__ import annotations

import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_sync_db():
    """Return a synchronous SQLAlchemy session for use inside Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings

    engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine)()


@celery_app.task(
    name="notification.send_notification",
    queue="notification",
    bind=True,
    acks_late=True,
    max_retries=3,
    default_retry_delay=10,
)
def send_notification(
    self,
    user_id: int,
    title: str,
    content: str | None,
    notification_type: str = "system",
    link: str | None = None,
    source_task_id: int | None = None,
) -> dict:
    """Create a notification for a user."""
    logger.info(
        "Sending notification: user_id=%s type=%s title=%s",
        user_id,
        notification_type,
        title,
    )

    session = _get_sync_db()
    try:
        from app.models.v4 import Notification

        notification = Notification(
            user_id=user_id,
            title=title,
            content=content,
            notification_type=notification_type,
            link=link,
            source_task_id=source_task_id,
        )
        session.add(notification)
        session.commit()
        session.refresh(notification)

        return {
            "notification_id": notification.id,
            "user_id": user_id,
            "type": notification_type,
        }
    except Exception as exc:
        session.rollback()
        logger.exception("Failed to create notification for user %d", user_id)
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            raise self.retry(exc=exc, countdown=10 * (2 ** retry_count))
        raise
    finally:
        session.close()


def create_notification_sync(
    user_id: int,
    title: str,
    content: str | None = None,
    notification_type: str = "system",
    link: str | None = None,
    source_task_id: int | None = None,
) -> None:
    """Convenience: call send_notification task (fire-and-forget)."""
    send_notification.delay(
        user_id=user_id,
        title=title,
        content=content,
        notification_type=notification_type,
        link=link,
        source_task_id=source_task_id,
    )
