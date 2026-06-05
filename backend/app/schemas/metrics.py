"""Core metrics API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MarginChangeSummary(BaseModel):
    continuing_structure_impact: float | None = None
    continuing_margin_impact: float | None = None
    new_impact: float | None = None
    exit_impact: float | None = None
    continuing_structure_impact_mom: float | None = None
    continuing_margin_impact_mom: float | None = None
    new_impact_mom: float | None = None
    exit_impact_mom: float | None = None


class MarginChangeItem(BaseModel):
    dimension_value: str
    category: str
    current_revenue: float | None = None
    current_share: float | None = None
    current_margin: float | None = None
    base_revenue: float | None = None
    base_share: float | None = None
    base_margin: float | None = None
    share_change: float | None = None
    margin_change: float | None = None
    structure_impact: float | None = None
    margin_impact: float | None = None
    total_impact: float | None = None
    # Per-category impact fields (only one is non-zero per row)
    continuing_structure_impact: float | None = None
    continuing_margin_impact: float | None = None
    new_impact: float | None = None
    exit_impact: float | None = None


class CoreMetricsSummary(BaseModel):
    revenue: float | None = None
    tax_excluded_cost: float | None = None
    gross_profit: float | None = None
    gross_margin: float | None = None
    gross_margin_yoy_change: float | None = None
    gross_margin_mom_change: float | None = None
    gross_margin_contribution: float | None = None
    customer_concentration_top3: float | None = None
    customer_concentration_top3_change: float | None = None
    product_concentration_top3: float | None = None
    customer_concentration_top10: float | None = None
    product_concentration_top10: float | None = None
    high_margin_order_ratio: float | None = None
    top_customer_share: float | None = None
    revenue_consecutive_growth: int | None = None
    revenue_consecutive_growth_avg: float | None = None
    gross_profit_consecutive_growth: int | None = None
    gross_profit_consecutive_growth_avg: float | None = None
    gross_margin_volatility: float | None = None
    gross_margin_volatility_change: float | None = None
    margin_change_analysis: list[MarginChangeItem] | None = None
    margin_change_summary: MarginChangeSummary | None = None
    revenue_yoy_growth: float | None = None
    revenue_yoy_change: float | None = None
    revenue_mom_change: float | None = None
    cost_yoy_growth: float | None = None
    gross_profit_yoy_growth: float | None = None
    gross_profit_yoy_change: float | None = None
    gross_profit_mom_change: float | None = None
    base_revenue: float | None = None
    base_gross_profit: float | None = None
    revenue_mom_growth: float | None = None
    gross_profit_mom_growth: float | None = None
    # New fields for analysis pages
    order_count: int | None = None
    achievement_rate: float | None = None
    loss_ratio: float | None = None
    core_market_line: str | None = None
    highest_value_market_line: str | None = None
    core_market_line_revenue: float | None = None
    highest_value_market_profit: float | None = None
    # Direct sign customer metrics
    direct_sign_revenue: float | None = None
    direct_sign_revenue_pct: float | None = None
    direct_sign_profit: float | None = None
    direct_sign_margin: float | None = None
    # Negative margin metrics
    negative_margin_order_ratio: float | None = None
    negative_margin_order_amount: float | None = None
    negative_margin_order_yoy_change: float | None = None
    negative_margin_order_mom_change: float | None = None
    negative_margin_product_ratio: float | None = None
    negative_margin_product_amount: float | None = None
    negative_margin_product_yoy_change: float | None = None
    negative_margin_product_mom_change: float | None = None


class BreakdownItem(BaseModel):
    dimension_value: str
    revenue: float | None = None
    tax_excluded_cost: float | None = None
    gross_profit: float | None = None
    gross_margin: float | None = None
    revenue_contribution: float | None = None
    gross_margin_contribution: float | None = None
    order_count: int | None = None
    avg_order_value: float | None = None  # 客单价(万元)
    neg_margin_order_count: int | None = None
    neg_margin_amount: float | None = None
    revenue_yoy_growth: float | None = None
    calculable: bool = True
    missing_fields: list[str] = Field(default_factory=list)


class TrendDataPoint(BaseModel):
    period: str
    revenue: float | None = None
    cost: float | None = None
    gross_profit: float | None = None
    gross_margin: float | None = None
    order_count: int | None = None
    revenue_mom_growth: float | None = None
    revenue_yoy_growth: float | None = None
    gross_profit_mom_growth: float | None = None
    gross_profit_yoy_growth: float | None = None
    gross_margin_mom_growth: float | None = None
    gross_margin_yoy_growth: float | None = None
    order_count_mom_growth: float | None = None
    order_count_yoy_growth: float | None = None


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
    product_line_breakdown: list[BreakdownItem] = Field(default_factory=list)
    customer_breakdown: list[BreakdownItem] = Field(default_factory=list)
    contract_type_breakdown: list[BreakdownItem] = Field(default_factory=list)
    trend_series: list[TrendDataPoint] = Field(default_factory=list)
    dimension_trend_series: list[DimensionTrendPoint] = Field(default_factory=list)
    data_quality: DataQuality
