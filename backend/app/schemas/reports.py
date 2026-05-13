"""Schemas for report generation API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ── Request schemas ────────────────────────────────────────────


class ReportCreateRequest(BaseModel):
    report_type: str = Field(..., description="daily / weekly / monthly")
    period: str = Field(default="", description="Report period, e.g. '2024-01' or '2024-Q1'")
    output_format: str = Field(default="pdf", description="pdf / word / excel")
    params: dict | None = Field(default=None, description="Extra generation parameters")
    parent_task_id: int | None = Field(default=None, description="Parent report task ID for retries")


class ReportCancelRequest(BaseModel):
    reason: str | None = Field(default=None, description="Cancellation reason")


# ── Response schemas ───────────────────────────────────────────


class ReportDetail(BaseModel):
    id: int
    user_id: int
    report_type: str
    status: str
    current_step: str
    period: str | None
    output_format: str
    file_path: str | None
    file_name: str | None
    error_message: str | None
    task_id: str | None
    celery_task_id: str | None
    retry_count: int
    parent_task_id: int | None
    params: dict | None
    created_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    items: list[ReportDetail] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
