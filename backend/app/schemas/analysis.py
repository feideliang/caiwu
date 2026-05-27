"""Schemas for per-page analysis recommendations."""

from pydantic import BaseModel, Field


class AnalysisRecommendationRequest(BaseModel):
    """Request for page-specific analysis recommendations."""
    page_type: str = Field(description="Page type: dashboard/trend/department/product/customer/core_metrics/insights/prediction")
    period: str | None = None
    period_compare_type: str | None = None  # yoy/mom/cumulative
    period_dimension: str | None = None  # monthly/quarterly/cumulative
    department: str | None = None
    product: str | None = None
    customer: str | None = None


class MetricRecommendation(BaseModel):
    """A single metric recommendation for the current page."""
    metric_name: str  # e.g., "毛利率", "收入同比", "客户集中度"
    metric_key: str  # e.g., "gross_margin", "revenue_yoy", "customer_concentration"
    description: str  # What this metric means
    current_value: float | None = None
    benchmark: float | None = None  # Reference value or threshold
    status: str = "normal"  # "normal" | "warning" | "critical"
    recommendation: str = ""  # Actionable suggestion based on current value


class AnomalyAlert(BaseModel):
    """Anomaly detected in current page data."""
    metric: str
    severity: str  # "low" | "medium" | "high"
    message: str  # Human-readable description
    value: float | None = None
    threshold: float | None = None


class AnalysisRecommendationResponse(BaseModel):
    """Response containing page-specific analysis recommendations."""
    page_type: str
    summary: str  # One-line summary of current page analysis focus
    metrics: list[MetricRecommendation] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    anomalies: list[AnomalyAlert] = Field(default_factory=list)
    drill_down_path: list[str] = Field(default_factory=list)  # Suggested next steps
