"""Query DSL and Dashboard BFF schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Query DSL ─────────────────────────────────────────────────

class FilterCondition(BaseModel):
    field: str
    operator: str  # eq, ne, gt, gte, lt, lte, in, like
    value: str | int | float | bool | list


class SortField(BaseModel):
    field: str
    order: str = "asc"  # asc / desc


class QueryRequest(BaseModel):
    table: str  # logical table name (financial_data, insight, etc.)
    filters: list[FilterCondition] = Field(default_factory=list)
    sort: list[SortField] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    fields: list[str] | None = None  # None = all


class QueryResponse(BaseModel):
    rows: list[dict]
    total: int
    page: int
    page_size: int


# ── Dashboard BFF ─────────────────────────────────────────────

class DashboardBFFRequest(BaseModel):
    dashboard_id: int | None = None
    device_type: str = "web"  # web / mobile / tablet
    filter_view_id: int | None = None
    bypass_cache: bool = False
    period: str | None = None
    period_dimension: str | None = None  # monthly / quarterly / cumulative / custom
    period_start: str | None = None
    period_end: str | None = None
    period_compare_type: str | None = None  # yoy / mom / cumulative
    department: str | None = None  # filter by department/market line
    product: str | None = None  # filter by product line


class BreakdownItem(BaseModel):
    dimension_value: str
    revenue: float | None = None
    tax_excluded_cost: float | None = None
    gross_profit: float | None = None
    gross_margin: float | None = None
    revenue_contribution: float | None = None
    gross_margin_contribution: float | None = None
    order_count: int | None = None
    avg_order_value: float | None = None
    neg_margin_order_count: int | None = None
    neg_margin_amount: float | None = None
    revenue_yoy_growth: float | None = None
    revenue_mom_growth: float | None = None
    gross_profit_mom_growth: float | None = None
    calculable: bool = True
    missing_fields: list[str] = Field(default_factory=list)


class DimensionBreakdown(BaseModel):
    """Breakdown data for a specific dimension (department/product)."""
    dimension: str  # 'department' or 'product'
    items: list[BreakdownItem] = Field(default_factory=list)


class KpiData(BaseModel):
    revenue: float = 0
    cost: float = 0
    gross_profit: float = 0
    gross_margin: float = 0
    achievement_rate: float = 0
    # MoM (month-over-month) - already existed
    revenue_mom_growth: float | None = 0
    profit_mom_growth: float | None = 0
    # YoY (year-over-year)
    cost_yoy_growth: float | None = 0
    revenue_yoy_growth: float | None = 0
    profit_yoy_growth: float | None = 0
    gross_margin_yoy_change: float | None = 0
    # Cumulative YTD
    revenue_cumulative: float = 0
    profit_cumulative: float = 0
    revenue_cumulative_growth: float | None = 0
    profit_cumulative_growth: float | None = 0
    # Base period values (for YoY comparison)
    base_revenue: float = 0
    base_gross_profit: float = 0
    base_gross_margin: float = 0
    base_achievement_rate: float = 0
    # Trend series
    trend_series: list = Field(default_factory=list)


class ChartDataItem(BaseModel):
    id: int | None = None
    title: str | None = None
    type: str | None = None
    data: list[dict]
    options: dict | None = None


class DashboardBFFResponse(BaseModel):
    dashboard_id: int
    dashboard_name: str
    device_type: str
    kpis: KpiData
    charts: list[ChartDataItem]
    layout: dict | None
    updated_at: str
    department_breakdown: list[BreakdownItem] = Field(default_factory=list)
    product_breakdown: list[BreakdownItem] = Field(default_factory=list)
