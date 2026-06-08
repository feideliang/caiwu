"""create income_margin_detail wide table

Revision ID: c1d69a6c233f
Revises: b1d69a6c233e
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "c1d69a6c233f"
down_revision = "b1d69a6c233e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "income_margin_detail",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),

        # ── Period / Entity ──────────────────────────────────
        sa.Column("period", sa.String(32), nullable=False, index=True, comment="确认收入期间 YYYY-MM"),
        sa.Column("entity", sa.String(128), nullable=False, index=True, comment="销售BGBU/市场线"),

        # ── Order Info ───────────────────────────────────────
        sa.Column("order_register_date", sa.Date, nullable=True, comment="订单登记日期"),
        sa.Column("revenue_confirm_date", sa.Date, nullable=True, comment="确认收入日期"),
        sa.Column("order_id", sa.String(64), nullable=True, index=True, comment="订单编号"),
        sa.Column("contract_no", sa.String(128), nullable=True, comment="电子商务合同号"),
        sa.Column("order_category", sa.String(64), nullable=True, comment="订单分类"),
        sa.Column("order_header_type", sa.String(64), nullable=True, comment="订单头类型"),
        sa.Column("order_customer", sa.String(256), nullable=True, comment="订单客户"),
        sa.Column("sequence_no", sa.String(32), nullable=True, comment="序号"),
        sa.Column("order_amount", sa.Numeric(20, 2), nullable=True, comment="订单金额"),
        sa.Column("order_qty", sa.Integer, nullable=True, comment="订单数量"),

        # ── Company / HR Organization ────────────────────────
        sa.Column("company", sa.String(128), nullable=True, comment="公司"),
        sa.Column("hr_dept_code", sa.String(64), nullable=True, comment="HR部门编码"),
        sa.Column("hr_department", sa.String(256), nullable=True, comment="HR部门名称"),
        sa.Column("sales_department", sa.String(256), nullable=True, comment="销售部门"),
        sa.Column("sales_person_code", sa.String(64), nullable=True, comment="业务员工号"),
        sa.Column("sales_person", sa.String(128), nullable=True, comment="业务员名称"),

        # ── Product Hierarchy ────────────────────────────────
        sa.Column("product_category", sa.String(128), nullable=True, comment="产品大类"),
        sa.Column("product_classification", sa.String(128), nullable=True, comment="产品分类"),
        sa.Column("product_bu_code", sa.String(64), nullable=True, comment="产品事业部代码"),
        sa.Column("product_bu_name", sa.String(256), nullable=True, comment="产品事业部名称"),
        sa.Column("product_bgbu", sa.String(128), nullable=True, comment="产品归属BGBU"),
        sa.Column("product_org", sa.String(256), nullable=True, comment="产品所属组织"),
        sa.Column("series", sa.String(256), nullable=True, comment="产品系列"),
        sa.Column("product_bgbu", sa.String(256), nullable=True, comment="产品线"),
        sa.Column("product_family", sa.String(256), nullable=True, comment="产品族"),
        sa.Column("sales_product_code", sa.String(128), nullable=True, comment="销售产品代码"),
        sa.Column("sales_product_name", sa.String(256), nullable=True, comment="销售产品名称"),
        sa.Column("material_code", sa.String(128), nullable=True, comment="物料编码"),
        sa.Column("material_desc", sa.Text, nullable=True, comment="物料描述"),
        sa.Column("material_cost_category", sa.String(128), nullable=True, comment="物料成本大类"),

        # ── Cost Classification ──────────────────────────────
        sa.Column("cost_class_1", sa.String(128), nullable=True, comment="一级成本分类"),
        sa.Column("cost_class_2", sa.String(128), nullable=True, comment="二级成本分类"),
        sa.Column("cost_class_3", sa.String(128), nullable=True, comment="三级成本分类"),
        sa.Column("cost_category", sa.String(128), nullable=True, comment="成本大类"),

        # ── Customer ─────────────────────────────────────────
        sa.Column("ncc_customer_code", sa.String(64), nullable=True, comment="NCC客户编码"),
        sa.Column("customer", sa.String(256), nullable=True, index=True, comment="客户名称"),
        sa.Column("invoice_customer", sa.String(256), nullable=True, comment="开票客户简称"),
        sa.Column("invoice_name", sa.String(256), nullable=True, comment="开票名称"),
        sa.Column("final_customer", sa.String(256), nullable=True, comment="最终客户名称"),
        sa.Column("superior_name", sa.String(256), nullable=True, comment="上级名称"),
        sa.Column("contract_type", sa.String(64), nullable=True, comment="客户签约类型"),
        sa.Column("contract_type_merged", sa.String(64), nullable=True, comment="客户签约类型(合并)"),
        sa.Column("customer_supplied_original", sa.String(64), nullable=True, comment="客供/逆售_原始"),
        sa.Column("customer_supplied_other", sa.String(64), nullable=True, comment="客供/逆售（其他业务）"),

        # ── Geography / Market ───────────────────────────────
        sa.Column("province", sa.String(64), nullable=True, comment="省份名称"),
        sa.Column("market_segment", sa.String(256), nullable=True, comment="细分市场说明"),
        sa.Column("region", sa.String(128), nullable=True, comment="区域"),
        sa.Column("bgbu", sa.String(64), nullable=True, comment="市场线BGBU"),
        sa.Column("business_type", sa.String(64), nullable=True, comment="主营/其他业务"),

        # ── Project / Application ────────────────────────────
        sa.Column("project_name", sa.String(256), nullable=True, comment="项目名称"),
        sa.Column("application_scenario", sa.String(256), nullable=True, comment="应用场合名称"),
        sa.Column("summary_name", sa.String(256), nullable=True, comment="合计名称"),

        # ── Invoice ──────────────────────────────────────────
        sa.Column("invoice_status", sa.String(64), nullable=True, comment="实际开票状态"),
        sa.Column("invoice_customer_short", sa.String(256), nullable=True, comment="开票客户简称(备用)"),

        # ── Currency / Exchange ──────────────────────────────
        sa.Column("currency", sa.String(16), nullable=True, comment="币种"),
        sa.Column("exchange_rate_local", sa.Numeric(18, 8), nullable=True, comment="原币对本币的汇率"),
        sa.Column("exchange_rate_rmb", sa.Numeric(18, 8), nullable=True, comment="原币对人民币的汇率"),
        sa.Column("tax_rate", sa.Numeric(10, 4), nullable=True, comment="税率"),

        # ── Financial Metrics (Tax-Excluded) ────────────────
        sa.Column("revenue_amount", sa.Numeric(20, 2), nullable=True, comment="收入金额(人民币)"),
        sa.Column("revenue_amount_local", sa.Numeric(20, 2), nullable=True, comment="收入金额(本币)"),
        sa.Column("revenue_amount_original", sa.Numeric(20, 2), nullable=True, comment="收入金额(原币)"),
        sa.Column("revenue_qty", sa.Integer, nullable=True, comment="收入数量"),
        sa.Column("cost_amount", sa.Numeric(20, 2), nullable=True, comment="不含税成本"),
        sa.Column("unit_cost_ex_tax", sa.Numeric(20, 4), nullable=True, comment="不含税单位成本"),
        sa.Column("gross_profit_amount", sa.Numeric(20, 2), nullable=True, comment="不含税毛利"),
        sa.Column("gross_margin_pct", sa.Numeric(10, 4), nullable=True, comment="毛利率"),

        # ── Financial Metrics (Tax-Included) ────────────────
        sa.Column("cost_incl_tax", sa.Numeric(20, 2), nullable=True, comment="含税成本"),
        sa.Column("unit_cost_incl_tax", sa.Numeric(20, 4), nullable=True, comment="含税单位成本"),
        sa.Column("gross_profit_incl_tax", sa.Numeric(20, 2), nullable=True, comment="含税毛利"),
        sa.Column("sales_amount_incl_tax_local", sa.Numeric(20, 2), nullable=True, comment="含税销售金额(本币)"),
        sa.Column("sales_amount_incl_tax_rmb", sa.Numeric(20, 2), nullable=True, comment="含税销售金额(人民币)"),
        sa.Column("sales_amount_incl_tax_original", sa.Numeric(20, 2), nullable=True, comment="含税销售金额(原币)"),
        sa.Column("tax_amount_local", sa.Numeric(20, 2), nullable=True, comment="税额(本币)"),
        sa.Column("sales_type", sa.String(32), nullable=True, comment="内销/外销"),

        # ── Revenue Year/Month (for period construction) ─────
        sa.Column("revenue_year", sa.Integer, nullable=True, comment="确认收入年"),
        sa.Column("revenue_month", sa.Integer, nullable=True, comment="确认收入月"),

        # ── Raw data snapshot ────────────────────────────────
        sa.Column("raw_data", JSONB, nullable=True, comment="完整原始行数据"),

        # ── Audit ────────────────────────────────────────────
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Composite indexes for common query patterns
    op.create_index("ix_imd_period_entity", "income_margin_detail", ["period", "entity"])
    op.create_index("ix_imd_customer_period", "income_margin_detail", ["customer", "period"])
    op.create_index("ix_imd_product_bgbu_period", "income_margin_detail", ["product_bgbu", "period"])
    op.create_index("ix_imd_bgbu_period", "income_margin_detail", ["bgbu", "period"])


def downgrade() -> None:
    op.drop_index("ix_imd_bgbu_period", table_name="income_margin_detail")
    op.drop_index("ix_imd_product_bgbu_period", table_name="income_margin_detail")
    op.drop_index("ix_imd_customer_period", table_name="income_margin_detail")
    op.drop_index("ix_imd_period_entity", table_name="income_margin_detail")
    op.drop_table("income_margin_detail")