"""Filter-related Pydantic schemas: filter-options and filter-views."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FilterCondition(BaseModel):
    field: str
    operator: str
    value: object


# ── Filter Options ──────────────────────────────────────────

class FilterOptionsRequest(BaseModel):
    dimension: str = Field(
        description="Dimension to fetch options for: period / entity / metric_name / department / product"
    )
    prefix: str | None = Field(default=None, description="Optional prefix filter for search-as-you-type")


class FilterOptionsResponse(BaseModel):
    dimension: str
    options: list[str]
    total: int


# ── Filter Views ────────────────────────────────────────────

class FilterViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    dashboard_id: int | None = None
    filters: dict | None = Field(default=None, description="{field: condition} filter map")
    conditions: list[FilterCondition] | None = None
    logic: str = "AND"
    is_public: bool = False


class FilterViewRead(BaseModel):
    id: int
    name: str
    dashboard_id: int | None
    filters: dict | None = None
    conditions: list[FilterCondition] = Field(default_factory=list)
    logic: str = "AND"
    is_public: bool
    user_id: int
    created_at: datetime | None

    model_config = {"from_attributes": True}


class FilterViewListResponse(BaseModel):
    items: list[FilterViewRead]
    total: int
