"""Core (original 9) SQLAlchemy models."""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base with standard audit columns."""
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ── Enums ─────────────────────────────────────────────────────

class DataSourceType(str, enum.Enum):
    BI_PLATFORM = "bi_platform"
    ERP = "erp"
    INTERNAL_SYSTEM = "internal_system"
    EXCEL = "excel"
    EMAIL_IMAP = "email_imap"


class SyncStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class QualityStatus(str, enum.Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


# ── 1. financial_data ─────────────────────────────────────────

class FinancialData(Base):
    __tablename__ = "financial_data"
    __table_args__ = (
        Index("ix_financial_data_period_metric", "period", "metric_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("data_batch.id"), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_unit: Mapped[str] = mapped_column(String(32), nullable=True)
    period: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # e.g. "2024-Q1"
    entity: Mapped[str | None] = mapped_column(String(128))  # company / department
    tags: Mapped[dict | None] = mapped_column(JSONB)  # jsonb for fast ->> extraction
    raw_row: Mapped[dict | None] = mapped_column(JSONB)  # full Excel row snapshot
    bucket: Mapped[str | None] = mapped_column(String(32), index=True)  # pre-computed: revenue/cost/gross_profit/target_revenue


# ── 2. data_batch ─────────────────────────────────────────────

class DataBatch(Base):
    __tablename__ = "data_batch"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_source.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[SyncStatus] = mapped_column(Enum(SyncStatus), default=SyncStatus.PENDING)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    file_name: Mapped[str | None] = mapped_column(String(256))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


# ── 3. data_source ────────────────────────────────────────────

class DataSource(Base):
    __tablename__ = "data_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[DataSourceType] = mapped_column(Enum(DataSourceType), nullable=False)
    connection_config: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # higher = higher priority


# ── 4. data_quality_log ───────────────────────────────────────

class DataQualityLog(Base):
    __tablename__ = "data_quality_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("data_batch.id"), nullable=True)
    status: Mapped[QualityStatus] = mapped_column(Enum(QualityStatus), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(128))
    detail: Mapped[str | None] = mapped_column(Text)
    affected_rows: Mapped[int] = mapped_column(Integer, default=0)


# ── 5. chart_config ──────────────────────────────────────────

class ChartConfig(Base):
    __tablename__ = "chart_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    chart_type: Mapped[str] = mapped_column(String(64), nullable=False)  # line, bar, pie, ...
    data_source_ids: Mapped[list[int] | None] = mapped_column(JSON)
    config: Mapped[dict | None] = mapped_column(JSON)  # chart-specific config
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


# ── 6. dashboard_layout ───────────────────────────────────────

class DashboardLayout(Base):
    __tablename__ = "dashboard_layout"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), default="web")  # web / mobile / tablet
    chart_ids: Mapped[list[int] | None] = mapped_column(JSON)
    layout_config: Mapped[dict | None] = mapped_column(JSON)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


# ── 7. user_preference ────────────────────────────────────────

class UserPreference(Base):
    __tablename__ = "user_preference"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    theme: Mapped[str] = mapped_column(String(32), default="light")
    default_device: Mapped[str] = mapped_column(String(32), default="web")
    preferences: Mapped[dict | None] = mapped_column(JSON)


# ── 8. system_config ──────────────────────────────────────────

class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(256))


# ── 10. knowledge_rule ────────────────────────────────────────

class KnowledgeRule(Base):
    """Business rules for AI chat — stored in PG + Qdrant for RAG retrieval."""
    __tablename__ = "knowledge_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_section: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    qdrant_point_id: Mapped[str | None] = mapped_column(String(36))  # UUID in Qdrant

    # ── Structured rule fields for engine execution ──
    rule_code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_executable: Mapped[bool] = mapped_column(default=False, server_default="false")


# ── 11. income_margin_detail (wide table) ─────────────────────

class IncomeMarginDetail(Base):
    """Wide table matching Excel income/margin detail layout 1:1.

    Designed for pandas-based import; each Excel row maps to one row.
    Dimension tables and financial_data metrics are derived via sync flows.
    """
    __tablename__ = "income_margin_detail"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # ── Period / Entity ──
    period: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # ── Order Info ──
    order_register_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    revenue_confirm_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(64), index=True)
    contract_no: Mapped[str | None] = mapped_column(String(128))
    order_category: Mapped[str | None] = mapped_column(String(64))
    order_header_type: Mapped[str | None] = mapped_column(String(64))
    order_customer: Mapped[str | None] = mapped_column(String(256))
    sequence_no: Mapped[str | None] = mapped_column(String(32))
    order_amount: Mapped[float | None] = mapped_column(Numeric(20, 2))
    order_qty: Mapped[int | None] = mapped_column(Integer)

    # ── Company / HR ──
    company: Mapped[str | None] = mapped_column(String(128))
    hr_dept_code: Mapped[str | None] = mapped_column(String(64))
    hr_department: Mapped[str | None] = mapped_column(String(256))
    sales_department: Mapped[str | None] = mapped_column(String(256))
    sales_person_code: Mapped[str | None] = mapped_column(String(64))
    sales_person: Mapped[str | None] = mapped_column(String(128))

    # ── Product Hierarchy ──
    product_category: Mapped[str | None] = mapped_column(String(128))
    product_classification: Mapped[str | None] = mapped_column(String(128))
    product_bu_code: Mapped[str | None] = mapped_column(String(64))
    product_bu_name: Mapped[str | None] = mapped_column(String(256))
    product_bgbu_value: Mapped[str | None] = mapped_column(String(128), name="product_bgbu")
    product_org: Mapped[str | None] = mapped_column(String(256))
    series: Mapped[str | None] = mapped_column(String(256))
    product_line: Mapped[str | None] = mapped_column(String(256))
    product_family: Mapped[str | None] = mapped_column(String(256))
    sales_product_code: Mapped[str | None] = mapped_column(String(128))
    sales_product_name: Mapped[str | None] = mapped_column(String(256))
    material_code: Mapped[str | None] = mapped_column(String(128))
    material_desc: Mapped[str | None] = mapped_column(Text)
    material_cost_category: Mapped[str | None] = mapped_column(String(128))

    # ── Cost Classification ──
    cost_class_1: Mapped[str | None] = mapped_column(String(128))
    cost_class_2: Mapped[str | None] = mapped_column(String(128))
    cost_class_3: Mapped[str | None] = mapped_column(String(128))
    cost_category: Mapped[str | None] = mapped_column(String(128))

    # ── Customer ──
    ncc_customer_code: Mapped[str | None] = mapped_column(String(64))
    customer: Mapped[str | None] = mapped_column(String(256), index=True)
    invoice_customer: Mapped[str | None] = mapped_column(String(256))
    invoice_name: Mapped[str | None] = mapped_column(String(256))
    final_customer: Mapped[str | None] = mapped_column(String(256))
    superior_name: Mapped[str | None] = mapped_column(String(256))
    contract_type: Mapped[str | None] = mapped_column(String(64))
    contract_type_merged: Mapped[str | None] = mapped_column(String(64))
    customer_supplied_original: Mapped[str | None] = mapped_column(String(64))
    customer_supplied_other: Mapped[str | None] = mapped_column(String(64))

    # ── Geography / Market ──
    province: Mapped[str | None] = mapped_column(String(64))
    market_segment: Mapped[str | None] = mapped_column(String(256))
    region: Mapped[str | None] = mapped_column(String(128))
    bgbu: Mapped[str | None] = mapped_column(String(64))
    business_type: Mapped[str | None] = mapped_column(String(64))

    # ── Project / Application ──
    project_name: Mapped[str | None] = mapped_column(String(256))
    application_scenario: Mapped[str | None] = mapped_column(String(256))
    summary_name: Mapped[str | None] = mapped_column(String(256))

    # ── Invoice ──
    invoice_status: Mapped[str | None] = mapped_column(String(64))
    invoice_customer_short: Mapped[str | None] = mapped_column(String(256))

    # ── Currency / Exchange ──
    currency: Mapped[str | None] = mapped_column(String(16))
    exchange_rate_local: Mapped[float | None] = mapped_column(Numeric(18, 8))
    exchange_rate_rmb: Mapped[float | None] = mapped_column(Numeric(18, 8))
    tax_rate: Mapped[float | None] = mapped_column(Numeric(10, 4))

    # ── Financial Metrics (Tax-Excluded) ──
    revenue_amount: Mapped[float | None] = mapped_column(Numeric(20, 2))
    revenue_amount_local: Mapped[float | None] = mapped_column(Numeric(20, 2))
    revenue_amount_original: Mapped[float | None] = mapped_column(Numeric(20, 2))
    revenue_qty: Mapped[int | None] = mapped_column(Integer)
    cost_amount: Mapped[float | None] = mapped_column(Numeric(20, 2))
    unit_cost_ex_tax: Mapped[float | None] = mapped_column(Numeric(20, 4))
    gross_profit_amount: Mapped[float | None] = mapped_column(Numeric(20, 2))
    gross_margin_pct: Mapped[float | None] = mapped_column(Numeric(10, 4))

    # ── Financial Metrics (Tax-Included) ──
    cost_incl_tax: Mapped[float | None] = mapped_column(Numeric(20, 2))
    unit_cost_incl_tax: Mapped[float | None] = mapped_column(Numeric(20, 4))
    gross_profit_incl_tax: Mapped[float | None] = mapped_column(Numeric(20, 2))
    sales_amount_incl_tax_local: Mapped[float | None] = mapped_column(Numeric(20, 2))
    sales_amount_incl_tax_rmb: Mapped[float | None] = mapped_column(Numeric(20, 2))
    sales_amount_incl_tax_original: Mapped[float | None] = mapped_column(Numeric(20, 2))
    tax_amount_local: Mapped[float | None] = mapped_column(Numeric(20, 2))
    sales_type: Mapped[str | None] = mapped_column(String(32))

    # ── Revenue Year/Month ──
    revenue_year: Mapped[int | None] = mapped_column(Integer)
    revenue_month: Mapped[int | None] = mapped_column(Integer)

    # ── Raw data ──
    raw_data: Mapped[dict | None] = mapped_column(JSON)


# ── 9. sync_job ───────────────────────────────────────────────

class SyncJob(Base):
    __tablename__ = "sync_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_source.id"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)  # full / incremental
    status: Mapped[SyncStatus] = mapped_column(Enum(SyncStatus), default=SyncStatus.PENDING)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)


# ── Aggregation Tables (pre-computed from income_margin_detail) ──

class _AggBase(DeclarativeBase):
    """Plain base for aggregation tables (no created_at/updated_at)."""


class AggPeriodSummary(_AggBase):
    """Monthly summary per department (bgbu) or 'ALL' for global."""
    __tablename__ = "agg_period_summary"

    period: Mapped[str] = mapped_column(String(10), primary_key=True)
    bgbu: Mapped[str] = mapped_column(String(64), primary_key=True, server_default="ALL")
    revenue: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")
    cost: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")
    gross_profit: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")
    order_count: Mapped[int] = mapped_column(Integer, server_default="0")
    direct_sign_revenue: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")
    direct_sign_cost: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")
    direct_sign_gp: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")
    target_revenue: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")


class AggDimensionSummary(_AggBase):
    """Dimension breakdown per period per department (bgbu) or 'ALL'."""
    __tablename__ = "agg_dimension_summary"

    period: Mapped[str] = mapped_column(String(10), primary_key=True)
    bgbu: Mapped[str] = mapped_column(String(64), primary_key=True, server_default="ALL")
    dim_type: Mapped[str] = mapped_column(String(32), primary_key=True)  # product_line, sales_product, customer, contract_type
    dim_value: Mapped[str] = mapped_column(String(512), primary_key=True)
    revenue: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")
    cost: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")
    gross_profit: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")
    order_count: Mapped[int] = mapped_column(Integer, server_default="0")

    __table_args__ = (
        Index("idx_ads_period_dim", "period", "dim_type"),
    )


class AggOrderSummary(_AggBase):
    """Order-level summary per period per department (bgbu) or 'ALL'."""
    __tablename__ = "agg_order_summary"

    period: Mapped[str] = mapped_column(String(10), primary_key=True)
    bgbu: Mapped[str] = mapped_column(String(64), primary_key=True, server_default="ALL")
    order_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    dim_dept: Mapped[str | None] = mapped_column(String(256))
    dim_product: Mapped[str | None] = mapped_column(String(128))
    revenue: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")
    cost: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")
    gross_profit: Mapped[float] = mapped_column(Numeric(20, 2), server_default="0")

    __table_args__ = (
        Index("idx_aos_period", "period"),
    )
