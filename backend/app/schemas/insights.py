"""Insight-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class InsightItem(BaseModel):
    id: int
    type: str
    title: str
    insight_type: str | None
    description: str | None = None
    severity: str = "medium"
    confidence: float = 0.8
    content: str | None
    status: str  # derived from data_json._status
    data_json: dict | None
    related_metric: str | None = None
    related_chart_id: int | None = None
    created_at: datetime | None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class InsightListResponse(BaseModel):
    items: list[InsightItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class InsightStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(read|process|ignore)$")
