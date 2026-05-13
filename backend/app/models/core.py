"""Core (original 9) SQLAlchemy models."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, func
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
    tags: Mapped[dict | None] = mapped_column(JSON)
    raw_row: Mapped[dict | None] = mapped_column(JSON)  # full Excel row snapshot


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
