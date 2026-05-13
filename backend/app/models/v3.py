"""V3.0 analytics models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.core import Base


# ── 1. insight ────────────────────────────────────────────────

class Insight(Base):
    __tablename__ = "insight"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    insight_type: Mapped[str] = mapped_column(String(64))  # anomaly / trend / correlation / summary
    content: Mapped[str] = mapped_column(Text)
    data_json: Mapped[dict | None] = mapped_column(JSONB)  # structured insight payload
    source_chart_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_by: Mapped[str] = mapped_column(String(64), default="ai")  # ai / manual
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


# ── 2. filter_view ────────────────────────────────────────────

class FilterView(Base):
    __tablename__ = "filter_view"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    dashboard_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {field: condition}
    is_public: Mapped[bool] = mapped_column(default=False)


# ── 3. correlation_result ─────────────────────────────────────

class CorrelationResult(Base):
    __tablename__ = "correlation_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_a: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_b: Mapped[str] = mapped_column(String(128), nullable=False)
    coefficient: Mapped[float] = mapped_column(Float, nullable=False)  # Pearson / Spearman
    p_value: Mapped[float | None] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer)
    period_start: Mapped[str | None] = mapped_column(String(32))
    period_end: Mapped[str | None] = mapped_column(String(32))
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── 4. correlation_calibration ────────────────────────────────

class CorrelationCalibration(Base):
    __tablename__ = "correlation_calibration"

    id: Mapped[int] = mapped_column(primary_key=True)
    correlation_id: Mapped[int] = mapped_column(ForeignKey("correlation_result.id"), nullable=False)
    calibrated_coefficient: Mapped[float] = mapped_column(Float, nullable=False)
    calibrated_by: Mapped[str] = mapped_column(String(64), default="ai")
    notes: Mapped[str | None] = mapped_column(Text)
    calibrated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── 5. prediction_result ──────────────────────────────────────

class PredictionResult(Base):
    __tablename__ = "prediction_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    prediction_type: Mapped[str] = mapped_column(String(64))  # forecast / anomaly_detection / trend
    horizon: Mapped[int] = mapped_column(Integer)  # number of periods ahead
    predicted_values: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {period: value}
    confidence_interval: Mapped[dict | None] = mapped_column(JSONB)
    model_name: Mapped[str | None] = mapped_column(String(64))
    accuracy_score: Mapped[float | None] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── 6. report_task ────────────────────────────────────────────

class ReportTask(Base):
    __tablename__ = "report_task"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)  # daily / weekly / monthly
    status: Mapped[str] = mapped_column(String(32), default="pending")
    # Phase 1C state-machine steps: pending / collecting_data / ai_analyzing / document_generating / completed / failed
    current_step: Mapped[str] = mapped_column(String(32), default="pending")
    period: Mapped[str | None] = mapped_column(String(32))
    output_format: Mapped[str] = mapped_column(String(16), default="pdf")  # pdf / word / excel
    file_path: Mapped[str | None] = mapped_column(String(512))
    file_name: Mapped[str | None] = mapped_column(String(256))
    error_message: Mapped[str | None] = mapped_column(Text)
    task_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # UUID for this task
    celery_task_id: Mapped[str | None] = mapped_column(String(128))  # Celery AsyncResult.id
    retry_count: Mapped[int] = mapped_column(default=0)
    parent_task_id: Mapped[int | None] = mapped_column(ForeignKey("report_task.id"), nullable=True)
    params: Mapped[dict | None] = mapped_column(JSONB)  # extra generation parameters
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
