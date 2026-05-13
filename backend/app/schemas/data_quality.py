"""Data quality schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class QualityRuleCount(BaseModel):
    rule_name: str
    status: str
    count: int


class QualitySummary(BaseModel):
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    pass_rate: float = 0
    by_rule: list[QualityRuleCount] = []


class QualityErrorItem(BaseModel):
    id: int
    batch_id: int
    rule_name: str
    status: str
    message: Optional[str] = None
    created_at: Optional[datetime] = None
