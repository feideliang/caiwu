"""Drilldown-related Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DrilldownSummary(BaseModel):
    report_id: int
    total_revenue: float
    total_cost: float
    total_profit: float
    profit_margin: float
    department_count: int


class DrilldownDepartment(BaseModel):
    dept_id: int
    dept_name: str
    revenue: float
    cost: float
    profit: float
    profit_margin: float
    product_count: int


class DrilldownProduct(BaseModel):
    product_id: int
    product_name: str
    revenue: float
    cost: float
    profit: float
    profit_margin: float


class DrilldownRecord(BaseModel):
    record_id: int
    period: str
    entity: str | None
    metric_name: str
    metric_value: float
    tags: dict | None
