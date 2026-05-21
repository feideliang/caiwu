"""add user.department column

Revision ID: b1d69a6c233e
Revises: a5a93b790558
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "b1d69a6c233e"
down_revision = "a5a93b790558"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("department", sa.String(128), nullable=True))
    op.create_index("ix_users_department", "users", ["department"])


def downgrade() -> None:
    op.drop_index("ix_users_department", table_name="users")
    op.drop_column("users", "department")