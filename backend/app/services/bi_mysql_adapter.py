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

# Maps MySQL column names to canonical names
MYSQL_COLUMN_MAP = {
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
    "不含税收入": "revenue_amount",
    "营业收入": "revenue_amount",
    "不含税成本": "cost_amount",
    "成本金额": "cost_amount",
    "营业成本": "cost_amount",
    "产品线": "product_line",
    "产品系列": "series",
    "产品": "product",
    "客户": "customer",
    "客户名称": "customer",
    "签约类型": "contract_type",
    "成本大类": "cost_category",
    "订单编号": "order_id",
    "合同编号": "contract_no",
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
        """
        rename_map = {k: v for k, v in MYSQL_COLUMN_MAP.items() if k in df.columns}
        df_mapped = df.rename(columns=rename_map)

        if "period" in df_mapped.columns:
            df_mapped["period"] = df_mapped["period"].apply(
                lambda v: str(v)[:7] if v else "2026-03"
            )

        tag_keys = {"product_line", "series", "product", "customer", "contract_type", "cost_category", "order_id", "contract_no"}
        records = []
        for _, row in df_mapped.iterrows():
            period = str(row.get("period", ""))[:7] or "2026-03"
            entity = str(row.get("entity", "")) or None
            tags = {k: str(row[k]) for k in tag_keys if k in row and pd.notna(row[k])}

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