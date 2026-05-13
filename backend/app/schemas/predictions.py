"""Schemas for prediction API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Request schemas ────────────────────────────────────────────


class PredictionCreateRequest(BaseModel):
    metric_name: str = Field(..., description="Financial metric to predict, e.g. 'revenue'")
    prediction_type: str = Field(
        default="forecast",
        description="revenue / gross_profit / dso / ar_aging",
    )
    horizon: int = Field(default=3, ge=1, le=12, description="Number of periods to forecast ahead")


# ── Response schemas ───────────────────────────────────────────


class ConfidenceBand(BaseModel):
    lower: float
    upper: float


class PredictionResultResponse(BaseModel):
    id: int
    metric_name: str
    prediction_type: str | None
    horizon: int | None
    forecast_values: dict = Field(default_factory=dict, description="{period: value}")
    confidence_band: dict = Field(default_factory=dict, description="{period: {lower, upper}}")
    model_type: str | None
    training_window: int | None
    mape: float | None
    accuracy_score: float | None
    accepted: bool = Field(default=True)
    rejected_reason: str | None = None
    computed_at: str | None

    model_config = {"from_attributes": True}
