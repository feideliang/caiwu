"""Core metrics API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CoreMetricsSummary(BaseModel):
    revenue: float | None = None
    tax_excluded_cost: float | None = None
    gross_profit: float | None = None
    gross_margin: float | None = None
    gross_margin_contribution: float | None = None
    customer_concentration_top3: float | None = None
    product_concentration_top3: float | None = None
    high_margin_order_ratio: float | None = None
    top_customer_share: float | None = None
    revenue_consecutive_growth: int | None = None
    gross_profit_consecutive_growth: int | None = None
    gross_margin_volatility: float | None = None
    margin_change_analysis: list[dict] | None = None  # 毛利率变动影响拆解
    revenue_yoy_growth: float | None = None
    gross_profit_yoy_growth: float | None = None
    revenue_mom_growth: float | None = None
    gross_profit_mom_growth: float | None = None
    # New fields for analysis pages
    order_count: int | None = None
    achievement_rate: float | None = None
    loss_ratio: float | None = None
    core_market_line: str | None = None
    highest_value_market_line: str | None = None


class BreakdownItem(BaseModel):
    dimension_value: str
    revenue: float | None = None
    tax_excluded_cost: float | None = None
    gross_profit: float | None = None
    gross_margin: float | None = None
    gross_margin_contribution: float | None = None
    order_count: int | None = None
    avg_order_value: float | None = None  # 客单价(万元)
    revenue_yoy_growth: float | None = None
    calculable: bool = True
    missing_fields: list[str] = Field(default_factory=list)


class TrendDataPoint(BaseModel):
    period: str
    revenue: float | None = None
    tax_excluded_cost: float | None = None
    gross_profit: float | None = None
    gross_margin: float | None = None
    revenue_mom_growth: float | None = None
    revenue_yoy_growth: float | None = None
    gross_profit_mom_growth: float | None = None
    gross_profit_yoy_growth: float | None = None


class DataQuality(BaseModel):
    calculable: bool = True
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DimensionTrendPoint(BaseModel):
    """Trend data point broken down by dimension (for stacked area charts)."""
    period: str
    dimension_value: str
    revenue: float | None = None
    gross_profit: float | None = None
    gross_margin: float | None = None


class CoreMetricsResponse(BaseModel):
    period: str | None = None
    dimension: str = "company"
    entity: str | None = None
    summary: CoreMetricsSummary
    breakdowns: list[BreakdownItem] = Field(default_factory=list)
    trend_series: list[TrendDataPoint] = Field(default_factory=list)
    dimension_trend_series: list[DimensionTrendPoint] = Field(default_factory=list)
    data_quality: DataQuality
