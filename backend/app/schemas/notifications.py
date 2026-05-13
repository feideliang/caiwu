"""Schemas for notification API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Response schemas ───────────────────────────────────────────


class NotificationDetail(BaseModel):
    id: int
    user_id: int
    title: str
    content: str | None
    notification_type: str
    is_read: bool
    link: str | None
    source_task_id: int | None
    created_at: str | None

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationDetail] = []
    total: int = 0
    unread_count: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
