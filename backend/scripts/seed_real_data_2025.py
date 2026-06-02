"""
从 Excel 导入真实收入/毛利明细数据到 income_margin_detail 大宽表。

使用 pandas (calamine 引擎) 读取，按列名映射后批量写入 PostgreSQL。
幂等：按 period 删除再插入。

用法:
  python scripts/seed_real_data_2025.py              # 执行导入
  python scripts/seed_real_data_2025.py --dry-run    # 仅预览，不写库
  python scripts/seed_real_data_2025.py --limit 1000 # 仅导入前 N 行（测试用）
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


# ── Column mapping: Excel Chinese → income_margin_detail column ──

COLUMN_MAP: dict[str, str] = {
    # Period / Entity
    "确认收入日期": "revenue_confirm_date",
    "确认日期": "revenue_confirm_date",
    "订单登记日期": "order_register_date",
    "销售BGBU": "entity",
    "BGBU": "entity",
    "市场线BGBU": "bgbu",
    "期间": "period_raw",
    "月份": "period_raw",

    # Order Info
    "订单编号": "order_id",
    "电子商务合同号": "contract_no",
    "合同编号": "contract_no",
    "订单分类": "order_category",
    "订单头类型": "order_header_type",
    "订单客户": "order_customer",
    "序号": "sequence_no",
    "订单金额": "order_amount",
    "订单数量": "order_qty",

    # Company / HR
    "公司": "company",
    "HR部门编码": "hr_dept_code",
    "HR部门名称": "hr_department",
    "销售部门": "sales_department",
    "业务员工号": "sales_person_code",
    "业务员名称": "sales_person",

    # Product Hierarchy
    "产品大类": "product_category",
    "产品分类": "product_classification",
    "产品事业部代码": "product_bu_code",
    "产品事业部名称": "product_bu_name",
    "产品归属BGBU": "product_bgbu",
    "产品所属组织": "product_org",
    "产品系列": "series",
    "产品线": "product_line",
    "产品族(产品线说明)": "product_family",
    "销售产品代码": "sales_product_code",
    "销售产品名称": "sales_product_name",
    "物料编码": "material_code",
    "物料描述": "material_desc",
    "物料成本大类": "material_cost_category",

    # Cost Classification
    "一级成本分类": "cost_class_1",
    "二级成本分类": "cost_class_2",
    "三级成本分类": "cost_class_3",
    "成本大类": "cost_category",
    "成本分类": "cost_category",

    # Customer
    "NCC客户编码": "ncc_customer_code",
    "客户名称": "customer",
    "客户": "customer",
    "开票客户简称": "invoice_customer",
    "开票名称": "invoice_name",
    "最终客户名称": "final_customer",
    "上级名称": "superior_name",
    "客户签约类型": "contract_type",
    "客户签约类型(合并)": "contract_type_merged",
    "客供/逆售_原始": "customer_supplied_original",
    "客供/逆售（其他业务）": "customer_supplied_other",
    "开票客户简称(备用)": "invoice_customer_short",

    # Geography / Market
    "省份名称": "province",
    "细分市场说明": "market_segment",
    "区域": "region",
    "主营/其他业务": "business_type",

    # Project / Application
    "项目名称": "project_name",
    "应用场合名称": "application_scenario",
    "合计名称": "summary_name",

    # Invoice
    "实际开票状态": "invoice_status",
    "实际开(金税)票状态": "invoice_status",

    # Currency / Exchange
    "币种": "currency",
    "原币对本币的汇率": "exchange_rate_local",
    "原币对人民币的汇率": "exchange_rate_rmb",
    "税率": "tax_rate",

    # Financial Metrics (Tax-Excluded)
    "收入金额": "revenue_amount",
    "收入金额(人民币)": "revenue_amount",
    "收入金额(本币)": "revenue_amount_local",
    "收入金额(原币)": "revenue_amount_original",
    "收入数量": "revenue_qty",
    "不含税成本": "cost_amount",
    "成本金额": "cost_amount",
    "不含税单位成本": "unit_cost_ex_tax",
    "不含税毛利": "gross_profit_amount",
    "毛利率": "gross_margin_pct",

    # Financial Metrics (Tax-Included)
    "含税成本": "cost_incl_tax",
    "含税单位成本": "unit_cost_incl_tax",
    "含税毛利": "gross_profit_incl_tax",
    "含税销售金额(本币)": "sales_amount_incl_tax_local",
    "含税销售金额(人民币)": "sales_amount_incl_tax_rmb",
    "含税销售金额(原币)": "sales_amount_incl_tax_original",
    "税额(本币)": "tax_amount_local",
    "内销/外销": "sales_type",

    # Revenue Year/Month
    "确认收入年": "revenue_year",
    "确认收入月": "revenue_month",

    # Fallback names
    "营业收入": "revenue_amount",
    "营业成本": "cost_amount",
    "订单金额（原币）": "order_amount",
    "订单金额（本币）": "order_amount",
}

# Data type per column
DATE_COLS = {"order_register_date", "revenue_confirm_date"}
INT_COLS = {"order_qty", "revenue_qty", "revenue_year", "revenue_month"}
FLOAT_COLS = {
    "order_amount", "exchange_rate_local", "exchange_rate_rmb", "tax_rate",
    "revenue_amount", "revenue_amount_local", "revenue_amount_original",
    "cost_amount", "unit_cost_ex_tax", "gross_profit_amount", "gross_margin_pct",
    "cost_incl_tax", "unit_cost_incl_tax", "gross_profit_incl_tax",
    "sales_amount_incl_tax_local", "sales_amount_incl_tax_rmb",
    "sales_amount_incl_tax_original", "tax_amount_local",
}

TARGET_PERIODS = [f"2025-{m:02d}" for m in range(1, 10)]
BATCH_SIZE = 50_000
DEFAULT_XLSX_PATH = Path(r"D:\日志\05\21\收入毛利明细数据for驾驶舱_202501-202509.xlsx")

# Column order for final DB insert
DB_COLS = [
    "period", "entity",
    "order_register_date", "revenue_confirm_date",
    "order_id", "contract_no", "order_category", "order_header_type",
    "order_customer", "sequence_no", "order_amount", "order_qty",
    "company", "hr_dept_code", "hr_department", "sales_department",
    "sales_person_code", "sales_person",
    "product_category", "product_classification", "product_bu_code",
    "product_bu_name", "product_bgbu", "product_org", "series",
    "product_line", "product_family", "sales_product_code",
    "sales_product_name", "material_code", "material_desc",
    "material_cost_category",
    "cost_class_1", "cost_class_2", "cost_class_3", "cost_category",
    "ncc_customer_code", "customer", "invoice_customer", "invoice_name",
    "final_customer", "superior_name", "contract_type",
    "contract_type_merged", "customer_supplied_original",
    "customer_supplied_other",
    "province", "market_segment", "region", "bgbu", "business_type",
    "project_name", "application_scenario", "summary_name",
    "invoice_status", "invoice_customer_short",
    "currency", "exchange_rate_local", "exchange_rate_rmb", "tax_rate",
    "revenue_amount", "revenue_amount_local", "revenue_amount_original",
    "revenue_qty", "cost_amount", "unit_cost_ex_tax",
    "gross_profit_amount", "gross_margin_pct",
    "cost_incl_tax", "unit_cost_incl_tax", "gross_profit_incl_tax",
    "sales_amount_incl_tax_local", "sales_amount_incl_tax_rmb",
    "sales_amount_incl_tax_original", "tax_amount_local", "sales_type",
    "revenue_year", "revenue_month",
]

TEXT_COLS = [c for c in DB_COLS if c not in DATE_COLS and c not in INT_COLS and c not in FLOAT_COLS
             and c not in ("period", "entity")]


# ── Helpers ─────────────────────────────────────────────────────

def build_col_rename_map(excel_headers: list[str]) -> tuple[dict[str, str], set[str]]:
    """Build a rename dict from actual Excel headers to English names.

    When multiple Chinese headers map to the same English name, the first
    occurrence wins.
    """
    rename = {}
    seen_eng: dict[str, str] = {}
    for h in excel_headers:
        hs = str(h).strip()
        if hs in COLUMN_MAP:
            eng = COLUMN_MAP[hs]
            if eng not in seen_eng:
                rename[hs] = eng
                seen_eng[eng] = hs
    unmapped = set(str(h).strip() for h in excel_headers) - set(COLUMN_MAP.keys())
    return rename, unmapped


def derive_period(df: pd.DataFrame) -> pd.Series:
    """Derive period YYYY-MM from available date columns."""
    p = pd.Series(index=df.index, dtype=str)
    # Try revenue_confirm_date first
    if "revenue_confirm_date" in df.columns:
        d = pd.to_datetime(df["revenue_confirm_date"], errors="coerce")
        p = d.dt.strftime("%Y-%m")
    # Fall back to period_raw
    if p.isna().all() and "period_raw" in df.columns:
        d = pd.to_datetime(df["period_raw"], errors="coerce")
        p = d.dt.strftime("%Y-%m")
    # Fall back to revenue_year + revenue_month
    if p.isna().any():
        yr = pd.to_numeric(df.get("revenue_year", pd.Series([None] * len(df))), errors="coerce")
        mo = pd.to_numeric(df.get("revenue_month", pd.Series([None] * len(df))), errors="coerce")
        mask = yr.notna() & mo.notna()
        p[mask] = yr[mask].astype(int).astype(str) + "-" + mo[mask].astype(int).map("{:02d}".format)
    return p


def safe_float_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(object).where(s.notna())


def safe_int_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(float).astype(object).where(s.notna())


# ── Database operations ────────────────────────────────────────

async def delete_target_periods(conn) -> int:
    result = await conn.execute(
        "DELETE FROM income_margin_detail WHERE period = ANY($1::varchar[])",
        TARGET_PERIODS,
    )
    parts = result.split()
    return int(parts[1]) if len(parts) == 2 and parts[0] == "DELETE" else 0


async def verify_data(conn):
    count = await conn.fetchval("SELECT COUNT(*) FROM income_margin_detail")
    print(f"  Total rows: {count:,}")

    periods = await conn.fetch(
        "SELECT period, COUNT(*) AS cnt FROM income_margin_detail "
        "GROUP BY period ORDER BY period",
    )
    print(f"  Rows by period ({len(periods)}):")
    for p in periods:
        print(f"    {p['period']}: {p['cnt']:,}")

    agg = await conn.fetchval(
        "SELECT SUM(revenue_amount) FROM income_margin_detail WHERE period LIKE '2025-%'",
    )
    print(f"  2025 total revenue_amount: {agg:,.2f}" if agg else "  2025 total revenue_amount: NULL")

    for yr in ("2024", "2026"):
        c = await conn.fetchval(
            "SELECT COUNT(*) FROM income_margin_detail WHERE period LIKE $1", f"{yr}-%"
        )
        print(f"  {yr} data preserved: {c:,} rows")


# ── Main ───────────────────────────────────────────────────────

async def seed(dry_run: bool = False, xlsx_path: str | None = None, limit: int | None = None) -> dict:
    if xlsx_path is None:
        xlsx_path = str(DEFAULT_XLSX_PATH)

    print(f"Reading Excel: {xlsx_path}")
    if not os.path.exists(xlsx_path):
        print(f"ERROR: File not found: {xlsx_path}")
        return {"status": "error", "message": "File not found"}

    t0 = time.time()

    # ── 1. Read ──
    df = pd.read_excel(xlsx_path, sheet_name=0, engine="calamine", dtype=str)
    print(f"Read: {df.shape[0]:,} rows × {df.shape[1]} cols  [{time.time() - t0:.0f}s]")

    if limit:
        df = df.head(limit)
        print(f"Limited to {limit} rows")

    # ── 2. Rename columns ──
    rename, unmapped = build_col_rename_map(df.columns)
    df.rename(columns=rename, inplace=True)
    # Keep only mapped columns
    mapped_cols = [c for c in df.columns if c in COLUMN_MAP.values()]
    df = df[mapped_cols]
    print(f"Mapped: {len(rename)} columns{', unmapped: ' + str(len(unmapped)) if unmapped else ''}")

    # ── 3. Derive period ──
    df["period"] = derive_period(df)
    before = len(df)
    df = df[df["period"].notna()].copy()
    skipped_period = before - len(df)
    print(f"Period derived: {len(df)} rows have valid period ({skipped_period} skipped)")

    # ── 4. Filter to target periods ──
    before = len(df)
    df = df[df["period"].isin(TARGET_PERIODS)]
    filtered = before - len(df)
    print(f"Target periods filter: {len(df)} rows kept ({filtered} excluded)")

    if df.empty:
        print("ERROR: No records for target periods!")
        return {"status": "error", "message": "No records"}

    # ── 6. Type conversions ──
    for col in FLOAT_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in INT_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").where(pd.to_numeric(df[col], errors="coerce").notna())
    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    # Clip numeric values to avoid DB overflow (Numeric(10,4) max ~999999)
    for col in ("gross_margin_pct", "tax_rate"):
        if col in df.columns:
            df[col] = df[col].clip(-999999.9999, 999999.9999)
    # Fill missing entity
    if "entity" not in df.columns:
        df["entity"] = None
    df["entity"] = df["entity"].fillna(df.get("product_bu_name")).fillna("UNKNOWN")

    # Ensure all DB_COLS exist (fill missing with None)
    for col in DB_COLS:
        if col not in df.columns:
            df[col] = None

    # ── 7. Build records as list of tuples ──
    df = df.where(df.notna(), None)
    records = [tuple(None if isinstance(v, float) and pd.isna(v) else v for v in row)
               for row in df[DB_COLS].itertuples(index=False)]

    elapsed = time.time() - t0
    period_counts = df["period"].value_counts().to_dict()
    print(f"\nSummary: {len(records):,} rows, periods {min(period_counts.keys())} ~ {max(period_counts.keys())}  [{elapsed:.0f}s]")

    if dry_run:
        print("\n=== DRY RUN — no database changes ===")
        return {"status": "dry_run", "records": len(records), "periods": sorted(period_counts.keys())}

    # ── 8. Database insert ──
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://learnhouse:learnhouse@localhost:5432/caiwu",
    )
    conn = await asyncpg.connect(database_url)

    try:
        print(f"\nDeleting existing data for {TARGET_PERIODS[0]} ~ {TARGET_PERIODS[-1]}...")
        t1 = time.time()
        deleted = await delete_target_periods(conn)
        print(f"Deleted {deleted:,} rows  [{time.time() - t1:.0f}s]")

        print(f"Inserting {len(records):,} rows in batches of {BATCH_SIZE:,}...")
        total = 0
        t2 = time.time()
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i: i + BATCH_SIZE]
            await conn.copy_records_to_table("income_margin_detail", columns=DB_COLS, records=batch)
            total += len(batch)
            print(f"  Inserted {total:,}/{len(records):,}  [{time.time() - t2:.0f}s]")

        print(f"\n=== Verification ===")
        await verify_data(conn)
    finally:
        await conn.close()

    total_elapsed = time.time() - t0
    print(f"\nDone! {total:,} rows  [{total_elapsed:.0f}s]")
    return {"status": "success", "inserted": total}


def main():
    parser = argparse.ArgumentParser(
        description="Import real financial data from Excel into income_margin_detail wide table"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB changes")
    parser.add_argument("--xlsx-path", default=None, help="Override default Excel file path")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows for testing")
    args = parser.parse_args()

    result = asyncio.run(seed(dry_run=args.dry_run, xlsx_path=args.xlsx_path, limit=args.limit))
    print(f"\nResult: {result}")


if __name__ == "__main__":
    main()