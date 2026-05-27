"""Data freshness Pydantic schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DataFreshnessResponse(BaseModel):
    last_sync_time: datetime | None
    data_range: dict | None
    status: str  # fresh / stale / error
    next_sync_at: datetime | None


# ── Knowledge Rule ──────────────────────────────────────────

class RuleCreate(BaseModel):
    category: str
    rule_text: str
    source_section: str | None = None
    is_active: bool = True
    rule_code: str | None = None
    threshold: float | None = None
    severity: str | None = None
    condition: str | None = None
    is_executable: bool = False


class RuleUpdate(BaseModel):
    category: str | None = None
    rule_text: str | None = None
    source_section: str | None = None
    is_active: bool | None = None
    rule_code: str | None = None
    threshold: float | None = None
    severity: str | None = None
    condition: str | None = None
    is_executable: bool | None = None


class RuleResponse(BaseModel):
    id: int
    category: str
    rule_text: str
    source_section: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
