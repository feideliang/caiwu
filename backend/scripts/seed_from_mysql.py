"""
Seed financial_data from BI MySQL database.

Reads from MySQL (income_margin_detail table), maps fields to financial_data schema,
syncs to PostgreSQL via DataSyncService.sync_incremental.

MySQL table structure (based on 收入毛利明细 Excel):
  - 确认收入日期  → period (YYYY-MM)
  - 销售BGBU     → entity
  - 产品线        → tags.product_line
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

# Maps MySQL column names to canonical financial_data columns
# Supports both Chinese and English aliases
MYSQL_COLUMN_MAP = {
    # period
    "确认收入日期": "period",
    "确认日期": "period",
    "期间": "period",
    "月份": "period",
    "period": "period",
    "date": "period",
    # entity
    "销售BGBU": "entity",
    "BGBU": "entity",
    "销售组织": "entity",
    "公司": "entity",
    "部门": "entity",
    "entity": "entity",
    "company": "entity",
    # revenue
    "收入金额": "revenue_amount",
    "收入金额(人民币)": "revenue_amount",
    "不含税收入": "revenue_amount",
    "营业收入": "revenue_amount",
    "revenue": "revenue_amount",
    # cost
    "不含税成本": "cost_amount",
    "成本金额": "cost_amount",
    "营业成本": "cost_amount",
    "cost": "cost_amount",
    # tag fields → stored in tags JSON
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
    """
    # Rename known columns
    rename_map = {k: v for k, v in MYSQL_COLUMN_MAP.items() if k in df.columns}
    df_mapped = df.rename(columns=rename_map)

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

        # Collect tag fields
        tag_keys = {"product_line", "series", "product", "customer", "contract_type", "cost_category", "order_id", "contract_no"}
        tags = {}
        for key in tag_keys:
            if key in row and pd.notna(row[key]):
                tags[key] = str(row[key])

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