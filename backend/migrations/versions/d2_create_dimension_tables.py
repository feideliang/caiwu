"""create dimension tables (customer/product/org/project)

Revision ID: d2_create_dimension_tables
Revises: c1d69a6c233f
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = "d2_create_dimension_tables"
down_revision = "c1d69a6c233f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DimCustomer
    op.create_table(
        "dim_customer",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("customer_name", sa.String(256), unique=True, nullable=False, index=True),
        sa.Column("ncc_customer_code", sa.String(64)),
        sa.Column("invoice_customer", sa.String(256)),
        sa.Column("invoice_name", sa.String(256)),
        sa.Column("final_customer", sa.String(256)),
        sa.Column("superior_name", sa.String(256)),
        sa.Column("contract_type", sa.String(64)),
        sa.Column("contract_type_merged", sa.String(64)),
        sa.Column("customer_supplied_original", sa.String(64)),
        sa.Column("customer_supplied_other", sa.String(64)),
        sa.Column("province", sa.String(64)),
        sa.Column("first_seen_period", sa.String(32)),
        sa.Column("last_seen_period", sa.String(32)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # DimProduct
    op.create_table(
        "dim_product",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("product_code", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("product_name", sa.String(256)),
        sa.Column("category", sa.String(128)),
        sa.Column("classification", sa.String(128)),
        sa.Column("bu_code", sa.String(64)),
        sa.Column("bu_name", sa.String(256)),
        sa.Column("bgbu", sa.String(128)),
        sa.Column("org", sa.String(256)),
        sa.Column("series", sa.String(256)),
        sa.Column("product_line", sa.String(256)),
        sa.Column("family", sa.String(256)),
        sa.Column("material_code", sa.String(128)),
        sa.Column("material_desc", sa.Text),
        sa.Column("material_cost_category", sa.String(128)),
        sa.Column("first_seen_period", sa.String(32)),
        sa.Column("last_seen_period", sa.String(32)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # DimOrganization
    op.create_table(
        "dim_organization",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("entity_name", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("company", sa.String(128)),
        sa.Column("hr_dept_code", sa.String(64)),
        sa.Column("hr_department", sa.String(256)),
        sa.Column("sales_department", sa.String(256)),
        sa.Column("bgbu", sa.String(64)),
        sa.Column("business_type", sa.String(64)),
        sa.Column("region", sa.String(128)),
        sa.Column("first_seen_period", sa.String(32)),
        sa.Column("last_seen_period", sa.String(32)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # DimProject
    op.create_table(
        "dim_project",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_name", sa.String(256), unique=True, nullable=False, index=True),
        sa.Column("application_scenario", sa.String(256)),
        sa.Column("summary_name", sa.String(256)),
        sa.Column("first_seen_period", sa.String(32)),
        sa.Column("last_seen_period", sa.String(32)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("dim_project")
    op.drop_table("dim_organization")
    op.drop_table("dim_product")
    op.drop_table("dim_customer")