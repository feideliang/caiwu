"""Audit log Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogRead(BaseModel):
    id: int
    user_id: int | None
    action: str
    resource_type: str | None
    resource_id: int | None
    detail: dict | None
    ip_address: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int


class AuditLogQueryParams(BaseModel):
    user_id: int | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
