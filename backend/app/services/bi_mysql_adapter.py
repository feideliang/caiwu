"""BI MySQL query adapter: read from MySQL and return as DataFrame.

Connects to BI MySQL database, auto-discovers tables, maps columns
to financial_data schema. Used by both seed script and API endpoints.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import pymysql

logger = logging.getLogger(__name__)

# Maps MySQL column names to canonical names.
# Non-financial columns (dimensions, tags) are prefixed with "tag:" and stored in tags JSON.
# Revenue/cost/financial metrics are mapped to canonical metric columns.
MYSQL_COLUMN_MAP = {
    # ── period / entity / financial metrics ──────────────────
    "确认收入日期": "period",
    "确认日期": "period",
    "期间": "period",
    "月份": "period",
    "销售BGBU": "entity",
    "BGBU": "entity",
    "销售组织": "entity",
    "公司": "entity",
    "收入金额": "revenue_amount",
    "收入金额(人民币)": "revenue_amount",
    "含税销售金额(人民币)": "revenue_amount",
    "不含税收入": "revenue_amount",
    "营业收入": "revenue_amount",
    "不含税成本": "cost_amount",
    "成本金额": "cost_amount",
    "营业成本": "cost_amount",
    # ── dimension fields → stored in tags JSON ───────────────
    "产品线": "tag:product_bgbu",
    "产品系列": "tag:series",
    "产品大类": "tag:product_category",
    "产品分类": "tag:product_classification",
    "产品族(产品线说明)": "tag:product_family",
    "产品事业部名称": "tag:product_bu_name",
    "产品事业部代码": "tag:product_bu_code",
    "产品所属组织": "tag:product_org",
    "产品归属BGBU": "tag:product_bgbu",
    "销售产品代码": "tag:sales_product_code",
    "销售产品名称": "tag:sales_product_name",
    "物料编码": "tag:material_code",
    "物料描述": "tag:material_desc",
    "物料成本大类": "tag:material_cost_category",
    "一级成本分类": "tag:cost_class_1",
    "二级成本分类": "tag:cost_class_2",
    "三级成本分类": "tag:cost_class_3",
    "成本大类": "tag:cost_category",
    "客户": "tag:customer",
    "客户名称": "tag:customer",
    "NCC客户编码": "tag:ncc_customer_code",
    "订单客户": "tag:order_customer",
    "开票客户简称": "tag:invoice_customer",
    "开票名称": "tag:invoice_name",
    "最终客户名称": "tag:final_customer",
    "上级名称": "tag:superior_name",
    "客户签约类型": "tag:contract_type",
    "订单编号": "tag:order_id",
    "电子商务合同号": "tag:contract_no",
    "合同编号": "tag:contract_no",
    "订单头类型": "tag:order_header_type",
    "订单分类": "tag:order_category",
    "内/外销": "tag:sales_type",
    "销售部门": "tag:sales_department",
    "HR部门编码": "tag:hr_dept_code",
    "HR部门名称": "tag:hr_department",
    "业务员名称": "tag:sales_person",
    "业务员工号": "tag:sales_person_code",
    "省份名称": "tag:province",
    "细分市场说明": "tag:market_segment",
    "应用场合名称": "tag:application_scenario",
    "项目名称": "tag:project_name",
    "序号": "tag:sequence_no",
    "确认收入年": "tag:revenue_year",
    "确认收入月": "tag:revenue_month",
    "订单登记日期": "tag:order_register_date",
    "币种": "tag:currency",
    "实际开(金税)票状态": "tag:invoice_status",
    "原币对本币的汇率": "tag:exchange_rate_local",
    "原币对人民币的汇率": "tag:exchange_rate_rmb",
    "税率": "tag:tax_rate",
    "订单数量": "tag:order_qty",
    "收入数量": "tag:revenue_qty",
    "订单金额": "tag:order_amount",
    "不含税单位成本": "tag:unit_cost_ex_tax",
    "含税单位成本": "tag:unit_cost_incl_tax",
    "含税成本": "tag:cost_incl_tax",
    "含税毛利": "tag:gross_profit_incl_tax",
    "含税销售金额(本币)": "tag:sales_amount_incl_tax_local",
    "含税销售金额(原币)": "tag:sales_amount_incl_tax_original",
    "收入金额(本币)": "tag:revenue_amount_local",
    "收入金额(原币)": "tag:revenue_amount_original",
    "税额(本币)": "tag:tax_amount_local",
}

LIKELY_TABLE_NAMES = [
    "income_margin_detail",
    "收入毛利明细",
    "financial_data",
    "revenue_cost_detail",
]


class BIMysqlAdapter:
    """Read data from BI MySQL database and return mapped DataFrame."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.host = config.get("host", "192.168.159.22")
        self.port = config.get("port", 33307)
        self.user = config.get("user", "app_caiwu")
        self.password = config.get("password", "123456")
        self.database = config.get("database", "caiwu")

    def _connect(self) -> pymysql.Connection:
        return pymysql.connect(
            host=self.host, port=self.port, user=self.user,
            password=self.password, database=self.database,
            charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
        )

    def discover_tables(self) -> list[dict]:
        """List all tables with column info and row counts."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES")
                tables = [row[list(row.keys())[0]] for row in cur.fetchall()]

            result = []
            for table in tables:
                with conn.cursor() as cur:
                    cur.execute(f"DESCRIBE `{table}`")
                    columns = cur.fetchall()
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table}`")
                    count = cur.fetchone()["cnt"]
                result.append({
                    "table": table,
                    "columns": [col["Field"] for col in columns],
                    "row_count": count,
                })
            return result
        finally:
            conn.close()

    def find_target_table(self, tables: list[dict]) -> dict | None:
        """Find the table matching income_margin_detail."""
        for name in LIKELY_TABLE_NAMES:
            for t in tables:
                if t["table"].lower() == name.lower():
                    return t
        # Fallback: table with period + revenue columns
        for t in tables:
            has_revenue = any("收入" in c or "revenue" in c.lower() for c in t["columns"])
            has_period = any("日期" in c or "期间" in c or "period" in c.lower() for c in t["columns"])
            if has_revenue and has_period and t["row_count"] > 0:
                return t
        return None

    def fetch_data(self, table_name: str) -> pd.DataFrame:
        """Read entire table into DataFrame."""
        conn = self._connect()
        try:
            return pd.read_sql(f"SELECT * FROM `{table_name}`", conn)
        finally:
            conn.close()

    def map_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map MySQL columns to financial_data multi-row schema.

        One source row → 4 financial_data rows (revenue, cost, gross_profit, profit_margin).
        Dimension fields (tag:*) are stored in tags JSON.
        """
        rename_map = {k: v for k, v in MYSQL_COLUMN_MAP.items() if k in df.columns}
        # Separate financial columns from tag fields
        fin_renames = {k: v for k, v in rename_map.items() if not v.startswith("tag:")}
        tag_renames = {k: v[4:] for k, v in rename_map.items() if v.startswith("tag:")}

        df_mapped = df.rename(columns=fin_renames)

        if "period" in df_mapped.columns:
            df_mapped["period"] = df_mapped["period"].apply(
                lambda v: str(v)[:7] if v else "2026-03"
            )
        elif "revenue_confirm_date" in df_mapped.columns:
            # Use revenue_confirm_date as period source
            df_mapped["period"] = df_mapped["revenue_confirm_date"].apply(
                lambda v: str(v)[:7] if v else None
            )

        records = []
        for _, row in df_mapped.iterrows():
            period = str(row.get("period", ""))[:7] or "2026-03"
            entity = str(row.get("entity", "")) or None

            # Build tags from tag fields
            tags = {}
            for tag_key in tag_renames.values():
                if tag_key in row and pd.notna(row[tag_key]):
                    tags[tag_key] = str(row[tag_key])

            revenue = float(row.get("revenue_amount", 0) or 0)
            cost = float(row.get("cost_amount", 0) or 0)
            profit = revenue - cost
            margin = (profit / revenue * 100) if revenue > 0 else 0.0

            for name, value in [("revenue", revenue), ("cost", cost), ("gross_profit", profit), ("profit_margin", margin)]:
                records.append({
                    "metric_name": name,
                    "metric_value": round(value, 2),
                    "period": period,
                    "entity": entity,
                    "tags": tags if tags else None,
                })

        return pd.DataFrame(records)

    def test_connection(self) -> dict[str, Any]:
        """Test MySQL connectivity."""
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.close()
            return {"status": "ok", "host": self.host, "database": self.database}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}