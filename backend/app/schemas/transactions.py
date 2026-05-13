"""Transaction analysis schemas."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ContractSummaryItem(BaseModel):
    entity: str
    total_ar: float = 0
    total_ap: float = 0
    net_exposure: float = 0
    period: str


class OrderSummaryItem(BaseModel):
    period: str
    revenue: float = 0
    cost: float = 0
    profit: float = 0


class ProjectSummaryItem(BaseModel):
    entity: str
    total_revenue: float = 0
    total_cost: float = 0
    profit_margin: float = 0
    period_span: str = ""


class AnomalyItem(BaseModel):
    metric_name: str
    period: str
    value: float = 0
    expected_mean: float = 0
    sigma_distance: float = 0
    entity: Optional[str] = None


class LargeAmountItem(BaseModel):
    metric_name: str
    metric_value: float = 0
    period: str
    entity: Optional[str] = None


class TransactionQueryParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    period: Optional[str] = None
    entity: Optional[str] = None
    period_from: Optional[str] = None
    period_to: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    threshold: float = Field(default=1000000, ge=0)
    metric_names: Optional[str] = None
