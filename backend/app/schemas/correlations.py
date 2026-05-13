"""Correlation-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ── Analyze ─────────────────────────────────────────────────

class CorrelationAnalyzeRequest(BaseModel):
    metric_a: str = Field(min_length=1, max_length=128)
    metric_b: str = Field(min_length=1, max_length=128)
    method: str = Field(default="pearson", description="pearson / spearman")
    period_start: str | None = None  # e.g. "2024-01"
    period_end: str | None = None
    request_ai_explanation: bool = Field(default=False)


class CorrelationDataPoint(BaseModel):
    period: str
    value_a: float
    value_b: float


class CorrelationAnalyzeResponse(BaseModel):
    id: int
    variable_x: str
    variable_y: str
    coefficient: float
    p_value: float | None
    sample_size: int
    period_start: str | None
    period_end: str | None
    strength: str  # strong / moderate / weak / none
    ai_explanation: str | None
    computed_at: datetime | None


# ── List ────────────────────────────────────────────────────

class CorrelationListResponse(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


# ── Calibrate ──────────────────────────────────────────────

class CorrelationCalibrateRequest(BaseModel):
    action: str = Field(pattern=r"^(confirm|doubt|reject)$")
    calibrated_coefficient: float | None = Field(default=None, description="Manual coefficient override")
    notes: str | None = None
