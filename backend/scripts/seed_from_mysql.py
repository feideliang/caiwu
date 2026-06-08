"""
Seed financial_data from BI MySQL database.

Reads from MySQL (income_margin_detail table), maps fields to financial_data schema,
syncs to PostgreSQL via DataSyncService.sync_incremental.

MySQL table structure (based on 收入毛利明细 Excel):
  - 确认收入日期  → period (YYYY-MM)
  - 销售BGBU     → entity
  - 产品线        → tags.product_bgbu
  - 产品系列      → tags.series
  - 客户          → tags.customer
  - 收入金额(人民币) → metric_value for metric_name='revenue'
  - 不含税成本    → metric_value for metric_name='cost'

Usage:
  python -m scripts.seed_from_mysql          # auto-discover tables + sync
  python -m scripts.seed_from_mysql --discover  # only discover, no sync
  python -m scripts.seed_from_mysql --full    # full sync (truncate + reload)
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pymysql
from sqlalchemy import create_engine, text


# ── MySQL field mapping ──────────────────────────────────────

# Maps MySQL column names to canonical financial_data columns.
# Dimension fields prefixed with "tag:" are stored in tags JSON.
MYSQL_COLUMN_MAP = {
    # period / entity
    "确认收入日期": "period",
    "确认日期": "period",
    "期间": "period",
    "月份": "period",
    "period": "period",
    "date": "period",
    "销售BGBU": "entity",
    "BGBU": "entity",
    "销售组织": "entity",
    "公司": "entity",
    "部门": "entity",
    "entity": "entity",
    "company": "entity",
    # revenue / cost
    "收入金额": "revenue_amount",
    "收入金额(人民币)": "revenue_amount",
    "含税销售金额(人民币)": "revenue_amount",
    "不含税收入": "revenue_amount",
    "营业收入": "revenue_amount",
    "revenue": "revenue_amount",
    "不含税成本": "cost_amount",
    "成本金额": "cost_amount",
    "营业成本": "cost_amount",
    "cost": "cost_amount",
    # tag fields → stored in tags JSON
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

# Columns that map to metric_name rows (one row per metric)
METRIC_AMOUNT_COLUMNS = {
    "revenue_amount": "revenue",
    "cost_amount": "cost",
}

# Known table names to try (in order of likelihood)
LIKELY_TABLE_NAMES = [
    "income_margin_detail",
    "收入毛利明细",
    "financial_data",
    "revenue_cost_detail",
    "收入成本明细",
]


def get_mysql_connection(config: dict) -> pymysql.Connection:
    """Create MySQL connection from config dict."""
    return pymysql.connect(
        host=config.get("host", "192.168.159.22"),
        port=config.get("port", 33307),
        user=config.get("user", "app_caiwu"),
        password=config.get("password", "123456"),
        database=config.get("database", "caiwu"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def discover_tables(conn: pymysql.Connection) -> list[dict]:
    """Discover all tables in MySQL database with column info."""
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
            "column_types": {col["Field"]: col["Type"] for col in columns},
            "row_count": count,
        })
    return result


def find_target_table(tables: list[dict]) -> dict | None:
    """Find the table that looks like income_margin_detail."""
    # Try known names first
    for name in LIKELY_TABLE_NAMES:
        for t in tables:
            if t["table"].lower() == name.lower():
                return t

    # Fallback: find table with period + revenue-like columns
    revenue_keywords = {"收入", "revenue", "金额", "amount"}
    period_keywords = {"日期", "期间", "period", "date", "月份"}
    for t in tables:
        cols_lower = set(c.lower() for c in t["columns"])
        has_revenue = any(kw in c for c in t["columns"] for kw in revenue_keywords)
        has_period = any(kw in c for c in t["columns"] for kw in period_keywords)
        if has_revenue and has_period and t["row_count"] > 0:
            return t

    return None


def mysql_to_dataframe(conn: pymysql.Connection, table_name: str) -> pd.DataFrame:
    """Read MySQL table into DataFrame."""
    sql = f"SELECT * FROM `{table_name}`"
    return pd.read_sql(sql, conn)


def map_mysql_to_financial(df: pd.DataFrame) -> pd.DataFrame:
    """Map MySQL columns to financial_data schema.

    One source row → multiple financial_data rows:
      - metric_name='revenue', metric_value=revenue_amount
      - metric_name='cost', metric_value=cost_amount
      - metric_name='gross_profit', metric_value=revenue-cost
      - metric_name='profit_margin', metric_value=margin%

    Dimension fields (tag:*) are stored in tags JSON.
    """
    # Separate financial renames from tag renames
    rename_map = {k: v for k, v in MYSQL_COLUMN_MAP.items() if k in df.columns}
    fin_renames = {k: v for k, v in rename_map.items() if not v.startswith("tag:")}
    tag_renames = {k: v[4:] for k, v in rename_map.items() if v.startswith("tag:")}

    df_mapped = df.rename(columns=fin_renames)

    # Normalize period to YYYY-MM format
    if "period" in df_mapped.columns:
        df_mapped["period"] = df_mapped["period"].apply(
            lambda v: str(v)[:7] if v else "2026-03"
        )

    # Build records: one source row → multiple metric rows
    records = []
    for _, row in df_mapped.iterrows():
        period = str(row.get("period", ""))[:7] or "2026-03"
        entity = str(row.get("entity", "")) or None

        # Collect tag fields from renamed columns
        tags = {}
        for tag_key in tag_renames.values():
            if tag_key in row and pd.notna(row[tag_key]):
                tags[tag_key] = str(row[tag_key])

        # Revenue row
        revenue = float(row.get("revenue_amount", 0) or 0)
        if revenue > 0:
            records.append({
                "metric_name": "revenue",
                "metric_value": round(revenue, 2),
                "period": period,
                "entity": entity,
                "tags": tags if tags else None,
            })

        # Cost row
        cost = float(row.get("cost_amount", 0) or 0)
        if cost > 0 or revenue > 0:
            records.append({
                "metric_name": "cost",
                "metric_value": round(cost, 2),
                "period": period,
                "entity": entity,
                "tags": tags if tags else None,
            })

        # Gross profit row
        profit = revenue - cost
        records.append({
            "metric_name": "gross_profit",
            "metric_value": round(profit, 2),
            "period": period,
            "entity": entity,
            "tags": tags if tags else None,
        })

        # Margin row
        margin = (profit / revenue * 100) if revenue > 0 else 0.0
        records.append({
            "metric_name": "profit_margin",
            "metric_value": round(margin, 2),
            "period": period,
            "entity": entity,
            "tags": tags if tags else None,
        })

    return pd.DataFrame(records)


async def sync_incremental(df: pd.DataFrame) -> dict:
    """Sync DataFrame to PG financial_data via DataSyncService."""
    from app.config import settings
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.services.data_sync import DataSyncService

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with AsyncSession(engine) as session:
        svc = DataSyncService(session)
        result = await svc.sync_incremental(df, source_id=1, file_name="mysql_bi_sync")
        await session.commit()
        return result


async def sync_full(df: pd.DataFrame) -> dict:
    """Full sync: truncate + reload."""
    from app.config import settings
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.services.data_sync import DataSyncService

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with AsyncSession(engine) as session:
        svc = DataSyncService(session)
        result = await svc.sync_full(df, source_id=1, file_name="mysql_bi_full_sync")
        await session.commit()
        return result


async def main(args):
    config = {
        "host": os.environ.get("BI_MYSQL_HOST", "192.168.159.22"),
        "port": int(os.environ.get("BI_MYSQL_PORT", "33307")),
        "user": os.environ.get("BI_MYSQL_USER", "app_caiwu"),
        "password": os.environ.get("BI_MYSQL_PASSWORD", "123456"),
        "database": os.environ.get("BI_MYSQL_DATABASE", "caiwu"),
    }

    print("Connecting to MySQL...")
    try:
        conn = get_mysql_connection(config)
    except Exception as exc:
        print(f"ERROR: Cannot connect to MySQL: {exc}")
        print("\nCheck your network. MySQL is on internal IP 192.168.159.22.")
        print("Set env vars if different: BI_MYSQL_HOST, BI_MYSQL_PORT, BI_MYSQL_USER, BI_MYSQL_PASSWORD, BI_MYSQL_DATABASE")
        return

    # Step 1: Discover tables
    print("\nDiscovering tables...")
    tables = discover_tables(conn)
    print(f"Found {len(tables)} tables:")
    for t in tables:
        print(f"  {t['table']}: {t['row_count']} rows, columns: {t['columns'][:8]}...")

    if args.discover:
        conn.close()
        return

    # Step 2: Find target table
    target = find_target_table(tables)
    if not target:
        print("\nERROR: No suitable table found. Available tables:")
        for t in tables:
            print(f"  {t['table']}: columns={t['columns']}")
        print("\nSet --table argument to specify the table name manually.")
        conn.close()
        return

    table_name = args.table or target["table"]
    print(f"\nUsing table: {table_name} ({target['row_count']} rows)")

    # Step 3: Read data
    print("Reading data from MySQL...")
    df_raw = mysql_to_dataframe(conn, table_name)
    conn.close()
    print(f"Read {len(df_raw)} rows, {len(df_raw.columns)} columns")
    print(f"Columns: {list(df_raw.columns)[:10]}")

    # Step 4: Map to financial_data schema
    print("Mapping columns to financial_data schema...")
    df_mapped = map_mysql_to_financial(df_raw)
    print(f"Generated {len(df_mapped)} financial_data records")

    if df_mapped.empty:
        print("ERROR: No records after mapping. Check column names.")
        return

    # Step 5: Clean data
    print("Cleaning data...")
    from app.services.data_cleaner import DataCleaner
    cleaner = DataCleaner()
    df_clean = cleaner.clean(df_mapped)
    print(f"Cleaned: {len(df_clean)} records")

    # Step 6: Sync to PG
    print(f"Syncing to PG (mode: {args.mode})...")
    if args.mode == "full":
        result = await sync_full(df_clean)
    else:
        result = await sync_incremental(df_clean)

    print(f"\nSync result:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    # Step 7: Verify
    print("\nVerifying PG data...")
    from app.config import settings
    import asyncpg
    pg_conn = await asyncpg.connect(
        settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    count = await pg_conn.fetchval("SELECT COUNT(*) FROM financial_data")
    periods = await pg_conn.fetch("SELECT DISTINCT period FROM financial_data ORDER BY period LIMIT 5")
    metrics = await pg_conn.fetch(
        "SELECT metric_name, COUNT(*), SUM(metric_value) FROM financial_data "
        "WHERE metric_name IN ('revenue','cost','gross_profit') GROUP BY metric_name"
    )
    print(f"  Total rows: {count:,}")
    print(f"  Periods: {[p['period'] for p in periods]}")
    for m in metrics:
        print(f"  {m['metric_name']}: count={m[1]:,}, sum={m[2]:,.2f}")
    await pg_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed financial_data from BI MySQL")
    parser.add_argument("--discover", action="store_true", help="Only discover tables, no sync")
    parser.add_argument("--mode", choices=["incremental", "full"], default="incremental")
    parser.add_argument("--table", type=str, help="MySQL table name (auto-detected if not specified)")
    args = parser.parse_args()
    asyncio.run(main(args))