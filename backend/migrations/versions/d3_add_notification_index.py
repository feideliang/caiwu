"""add notification composite index (user_id, created_at DESC)

Revision ID: d3_add_notification_index
Revises: d2_create_dimension_tables
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "d3_add_notification_index"
down_revision = "d2_create_dimension_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index for the primary notification query pattern:
    #   WHERE user_id = ? ORDER BY created_at DESC
    # This index was defined in the ORM model but never created in the database
    # (the initial migration omitted it and no subsequent migration added it).
    op.create_index(
        "ix_notification_user_created",
        "notification",
        ["user_id", sa.text("created_at DESC")],
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("ix_notification_user_created", table_name="notification")