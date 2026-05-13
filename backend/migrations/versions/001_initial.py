"""Create all tables for Phase 1A.

Revision ID: 001_initial
Revises:
Create Date: 2026-05-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Roles ─────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), unique=True, nullable=False),
        sa.Column("display_name", sa.String(128)),
        sa.Column("permissions", sa.JSON),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Seed default roles
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", sa.Integer),
            sa.column("name", sa.String),
            sa.column("display_name", sa.String),
            sa.column("permissions", sa.JSON),
        ),
        [
            {"id": 1, "name": "admin", "display_name": "Administrator", "permissions": ["*"]},
            {"id": 2, "name": "analyst", "display_name": "Analyst", "permissions": ["report:*", "dashboard:*", "data:*"]},
            {"id": 3, "name": "viewer", "display_name": "Viewer", "permissions": ["dashboard:*"]},
        ],
    )

    # ── Users ─────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(256), unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("last_login_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── financial_data ────────────────────────────────────
    op.create_table(
        "financial_data",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("batch_id", sa.Integer, sa.ForeignKey("data_batch.id")),
        sa.Column("metric_name", sa.String(128), nullable=False, index=True),
        sa.Column("metric_value", sa.Float, nullable=False),
        sa.Column("metric_unit", sa.String(32)),
        sa.Column("period", sa.String(32), nullable=False, index=True),
        sa.Column("entity", sa.String(128)),
        sa.Column("tags", sa.JSON),
        sa.Column("raw_row", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── data_batch ────────────────────────────────────────
    op.create_table(
        "data_batch",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("data_source.id")),
        sa.Column("batch_no", sa.String(64), unique=True, nullable=False),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("record_count", sa.Integer, default=0),
        sa.Column("file_name", sa.String(256)),
        sa.Column("processed_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── data_source ───────────────────────────────────────
    op.create_table(
        "data_source",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("connection_config", sa.JSON),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("last_sync_at", sa.DateTime),
        sa.Column("priority", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── data_quality_log ──────────────────────────────────
    op.create_table(
        "data_quality_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("batch_id", sa.Integer, sa.ForeignKey("data_batch.id")),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("rule_name", sa.String(128)),
        sa.Column("detail", sa.Text),
        sa.Column("affected_rows", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── chart_config ──────────────────────────────────────
    op.create_table(
        "chart_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("chart_type", sa.String(64), nullable=False),
        sa.Column("data_source_ids", sa.JSON),
        sa.Column("config", sa.JSON),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── dashboard_layout ──────────────────────────────────
    op.create_table(
        "dashboard_layout",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("device_type", sa.String(32), default="web"),
        sa.Column("chart_ids", sa.JSON),
        sa.Column("layout_config", sa.JSON),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── user_preference ───────────────────────────────────
    op.create_table(
        "user_preference",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("theme", sa.String(32), default="light"),
        sa.Column("default_device", sa.String(32), default="web"),
        sa.Column("preferences", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── system_config ─────────────────────────────────────
    op.create_table(
        "system_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(128), unique=True, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.String(256)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── sync_job ──────────────────────────────────────────
    op.create_table(
        "sync_job",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("data_source.id")),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("error_message", sa.Text),
        sa.Column("records_processed", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── V3.0: insight ─────────────────────────────────────
    op.create_table(
        "insight",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("insight_type", sa.String(64)),
        sa.Column("content", sa.Text),
        sa.Column("data_json", sa.JSON),
        sa.Column("source_chart_id", sa.Integer),
        sa.Column("generated_by", sa.String(64), default="ai"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── V3.0: filter_view ─────────────────────────────────
    op.create_table(
        "filter_view",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("dashboard_id", sa.Integer),
        sa.Column("filters", sa.JSON, nullable=False),
        sa.Column("is_public", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── V3.0: correlation_result ──────────────────────────
    op.create_table(
        "correlation_result",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("metric_a", sa.String(128), nullable=False),
        sa.Column("metric_b", sa.String(128), nullable=False),
        sa.Column("coefficient", sa.Float, nullable=False),
        sa.Column("p_value", sa.Float),
        sa.Column("sample_size", sa.Integer),
        sa.Column("period_start", sa.String(32)),
        sa.Column("period_end", sa.String(32)),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── V3.0: correlation_calibration ─────────────────────
    op.create_table(
        "correlation_calibration",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("correlation_id", sa.Integer, sa.ForeignKey("correlation_result.id"), nullable=False),
        sa.Column("calibrated_coefficient", sa.Float, nullable=False),
        sa.Column("calibrated_by", sa.String(64), default="ai"),
        sa.Column("notes", sa.Text),
        sa.Column("calibrated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── V3.0: prediction_result ───────────────────────────
    op.create_table(
        "prediction_result",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("metric_name", sa.String(128), nullable=False, index=True),
        sa.Column("prediction_type", sa.String(64)),
        sa.Column("horizon", sa.Integer),
        sa.Column("predicted_values", sa.JSON, nullable=False),
        sa.Column("confidence_interval", sa.JSON),
        sa.Column("model_name", sa.String(64)),
        sa.Column("accuracy_score", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── V3.0: report_task ─────────────────────────────────
    op.create_table(
        "report_task",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("report_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("current_step", sa.String(32), default="pending"),
        sa.Column("period", sa.String(32)),
        sa.Column("output_format", sa.String(16), default="pdf"),
        sa.Column("file_path", sa.String(512)),
        sa.Column("file_name", sa.String(256)),
        sa.Column("error_message", sa.Text),
        sa.Column("task_id", sa.String(64), unique=True),
        sa.Column("celery_task_id", sa.String(128)),
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("parent_task_id", sa.Integer, sa.ForeignKey("report_task.id")),
        sa.Column("params", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime),
    )

    # ── V4.0: audit_log ───────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64)),
        sa.Column("resource_id", sa.Integer),
        sa.Column("detail", sa.JSON),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(512)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), index=True),
    )

    # ── V4.0: notification ────────────────────────────────
    op.create_table(
        "notification",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("notification_type", sa.String(64)),
        sa.Column("is_read", sa.Boolean, default=False),
        sa.Column("link", sa.String(512)),
        sa.Column("source_task_id", sa.Integer),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("notification")
    op.drop_table("audit_log")
    op.drop_table("report_task")
    op.drop_table("prediction_result")
    op.drop_table("correlation_calibration")
    op.drop_table("correlation_result")
    op.drop_table("filter_view")
    op.drop_table("insight")
    op.drop_table("sync_job")
    op.drop_table("system_config")
    op.drop_table("user_preference")
    op.drop_table("dashboard_layout")
    op.drop_table("chart_config")
    op.drop_table("data_quality_log")
    op.drop_table("data_source")
    op.drop_table("data_batch")
    op.drop_table("financial_data")
    op.drop_table("users")
    op.drop_table("roles")
