"""
Import both Excel files into income_margin_detail.
Clears existing data first, then bulk imports.

Usage:
  python scripts/import_income_margin_xlsx.py
  python scripts/import_income_margin_xlsx.py --dry-run
"""

import argparse
import asyncio
import json
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import asyncpg
from dotenv import load_dotenv
import os
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

FILES = [
    # File 1 already imported (2025-01~09, 463,448 rows) — skip
    Path(r"D:\日志\05\21\收入毛利明细数据for驾驶舱_202510-202604.xlsx"),
]

# Excel column (Chinese) -> table column (English) mapping
COL_MAP = {
    "订单登记日期": "order_register_date",
    "确认收入日期": "revenue_confirm_date",
    "订单编号": "order_id",
    "电子商务合同号": "contract_no",
    "订单分类": "order_category",
    "订单头类型": "order_header_type",
    "订单客户": "order_customer",
    "序号": "sequence_no",
    "订单金额": "order_amount",
    "订单数量": "order_qty",
    "公司": "company",
    "HR部门编码": "hr_dept_code",
    "HR部门名称": "hr_department",
    "销售部门": "sales_department",
    "业务员工号": "sales_person_code",
    "业务员名称": "sales_person",
    "产品大类": "product_category",
    "产品分类": "product_classification",
    "产品事业部代码": "product_bu_code",
    "产品事业部名称": "product_bu_name",
    "产品所属事业部": "product_line",
    "产品所属组织": "product_org",
    "产品系列": "series",
    "产品线": "product_line",
    "产品族(产品线说明)": "product_family",
    "销售产品代码": "sales_product_code",
    "销售产品名称": "sales_product_name",
    "物料编码": "material_code",
    "物料描述": "material_desc",
    "物料成本大类": "material_cost_category",
    "一级成本分类": "cost_class_1",
    "二级成本分类": "cost_class_2",
    "三级成本分类": "cost_class_3",
    "NCC客户编码": "ncc_customer_code",
    "最终客户名称": "final_customer",
    "开票名称": "invoice_name",
    "开票客户简称": "invoice_customer_short",
    "上级名称": "superior_name",
    "客供/逆售_原始": "customer_supplied_original",
    "客供/逆售（其他业务）": "customer_supplied_other",
    "客户签约类型": "contract_type",
    "客户签约类型(合并)": "contract_type_merged",
    "省份名称": "province",
    "细分市场说明": "market_segment",
    "内销/外销": "region",
    "市场线BGBU": "bgbu",
    "主营/其他业务": "business_type",
    "项目名称": "project_name",
    "应用场合名称": "application_scenario",
    "实际开(金税)票状态": "invoice_status",
    "币种": "currency",
    "原币对本币的汇率": "exchange_rate_local",
    "原币对人民币的汇率": "exchange_rate_rmb",
    "税率": "tax_rate",
    "收入金额(本币)": "revenue_amount_local",
    "收入金额(人民币)": "revenue_amount",
    "收入金额(原币)": "revenue_amount_original",
    "收入数量": "revenue_qty",
    "不含税成本": "cost_amount",
    "不含税单位成本": "unit_cost_ex_tax",
    "不含税毛利": "gross_profit_amount",
    "毛利率": "gross_margin_pct",
    "含税成本": "cost_incl_tax",
    "含税单位成本": "unit_cost_incl_tax",
    "含税毛利": "gross_profit_incl_tax",
    "含税销售金额(本币)": "sales_amount_incl_tax_local",
    "含税销售金额(人民币)": "sales_amount_incl_tax_rmb",
    "含税销售金额(原币)": "sales_amount_incl_tax_original",
    "税额(本币)": "tax_amount_local",
    "确认收入年": "revenue_year",
    "确认收入月": "revenue_month",
}

# Columns that should be stored as-is in the table
TABLE_COLUMNS = [
    "period", "entity",
    "order_register_date", "revenue_confirm_date",
    "order_id", "contract_no", "order_category", "order_header_type",
    "order_customer", "sequence_no", "order_amount", "order_qty",
    "company", "hr_dept_code", "hr_department", "sales_department",
    "sales_person_code", "sales_person",
    "product_category", "product_classification", "product_bu_code",
    "product_bu_name", "product_line", "product_org", "series",
    "product_line", "product_family", "sales_product_code", "sales_product_name",
    "material_code", "material_desc", "material_cost_category",
    "cost_class_1", "cost_class_2", "cost_class_3",
    "ncc_customer_code", "customer", "invoice_customer", "invoice_name",
    "final_customer", "superior_name",
    "contract_type", "contract_type_merged",
    "customer_supplied_original", "customer_supplied_other",
    "province", "market_segment", "region", "bgbu", "business_type",
    "project_name", "application_scenario", "summary_name",
    "invoice_status", "invoice_customer_short",
    "currency", "exchange_rate_local", "exchange_rate_rmb", "tax_rate",
    "revenue_amount", "revenue_amount_local", "revenue_amount_original",
    "revenue_qty", "cost_amount", "unit_cost_ex_tax",
    "gross_profit_amount", "gross_margin_pct",
    "cost_incl_tax", "unit_cost_incl_tax", "gross_profit_incl_tax",
    "sales_amount_incl_tax_local", "sales_amount_incl_tax_rmb",
    "sales_amount_incl_tax_original", "tax_amount_local",
    "sales_type", "revenue_year", "revenue_month",
]


def _to_str(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return str(val).strip() or None


def _to_num(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _to_int(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


DATE_COLS = {"order_register_date", "revenue_confirm_date"}


def _to_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


NUMERIC_COLS = {
    "order_amount", "exchange_rate_local", "exchange_rate_rmb", "tax_rate",
    "revenue_amount", "revenue_amount_local", "revenue_amount_original",
    "cost_amount", "unit_cost_ex_tax", "gross_profit_amount", "gross_margin_pct",
    "cost_incl_tax", "unit_cost_incl_tax", "gross_profit_incl_tax",
    "sales_amount_incl_tax_local", "sales_amount_incl_tax_rmb",
    "sales_amount_incl_tax_original", "tax_amount_local",
}

INT_COLS = {"order_qty", "revenue_qty", "revenue_year", "revenue_month"}

# Columns to copy into table directly (skip raw_data for now to save space)
INSERT_COLUMNS = [c for c in TABLE_COLUMNS if c in {
    "period", "entity",
    "order_register_date", "revenue_confirm_date",
    "order_id", "contract_no", "order_category", "order_header_type",
    "order_customer", "sequence_no", "order_amount", "order_qty",
    "company", "hr_dept_code", "hr_department", "sales_department",
    "sales_person_code", "sales_person",
    "product_category", "product_classification", "product_bu_code",
    "product_bu_name", "product_line", "product_org", "series",
    "product_line", "product_family", "sales_product_code", "sales_product_name",
    "material_code", "material_desc", "material_cost_category",
    "cost_class_1", "cost_class_2", "cost_class_3",
    "ncc_customer_code", "final_customer",
    "invoice_name", "invoice_customer_short", "superior_name",
    "contract_type", "contract_type_merged",
    "customer_supplied_original", "customer_supplied_other",
    "province", "market_segment", "region", "bgbu", "business_type",
    "project_name", "application_scenario",
    "invoice_status",
    "currency", "exchange_rate_local", "exchange_rate_rmb", "tax_rate",
    "revenue_amount", "revenue_amount_local", "revenue_amount_original",
    "revenue_qty", "cost_amount", "unit_cost_ex_tax",
    "gross_profit_amount", "gross_margin_pct",
    "cost_incl_tax", "unit_cost_incl_tax", "gross_profit_incl_tax",
    "sales_amount_incl_tax_local", "sales_amount_incl_tax_rmb",
    "sales_amount_incl_tax_original", "tax_amount_local",
    "revenue_year", "revenue_month",
}]


def df_to_records(df: pd.DataFrame) -> list[tuple]:
    """Convert DataFrame to list of tuples for copy_records_to_table."""
    records = []
    for _, row in df.iterrows():
        # Derive period from 确认收入日期
        rcd = row.get("确认收入日期")
        if rcd is not None and not (isinstance(rcd, float) and pd.isna(rcd)):
            period = str(rcd)[:7]  # YYYY-MM
        else:
            year = row.get("确认收入年")
            month = row.get("确认收入月")
            if year and month and not (isinstance(year, float) and pd.isna(year)):
                period = f"{int(year)}-{int(month):02d}"
            else:
                period = "unknown"

        entity = _to_str(row.get("公司"))

        vals = [period, entity]
        for cn_name, en_name in COL_MAP.items():
            if en_name not in INSERT_COLUMNS[2:]:  # skip period, entity already added
                continue
            val = row.get(cn_name)
            if en_name in NUMERIC_COLS:
                vals.append(_to_num(val))
            elif en_name in INT_COLS:
                vals.append(_to_int(val))
            else:
                vals.append(_to_str(val))

        records.append(tuple(vals))
    return records


async def main(dry_run=False):
    db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    conn = await asyncpg.connect(db_url)
    t0 = time.time()

    if not dry_run:
        print("Deleting existing rows for periods >= 2025-10...")
        result = await conn.execute(
            "DELETE FROM income_margin_detail WHERE period >= '2025-10'"
        )
        print(f"  {result}")

    batch_size = 2_000
    grand_total = 0

    for fpath in FILES:
        print(f"\nReading {fpath.name} (pandas, this takes ~7 min for 350k rows)...")
        t1 = time.time()
        df = pd.read_excel(fpath, engine="openpyxl")
        print(f"  {len(df):,} rows, {len(df.columns)} cols  [{time.time()-t1:.1f}s]")

        if dry_run:
            print(f"  Cols: {list(df.columns[:10])}")
            continue

        print(f"  Converting and inserting...")
        t2 = time.time()
        batch: list[tuple] = []

        for _, row in df.iterrows():
            # Derive period from 确认收入日期
            rcd = row.get("确认收入日期")
            if rcd is not None and not (isinstance(rcd, float) and pd.isna(rcd)):
                period = str(rcd)[:7]
            else:
                year = row.get("确认收入年")
                month = row.get("确认收入月")
                if year and month and not (isinstance(year, float) and pd.isna(year)):
                    period = f"{int(year)}-{int(month):02d}"
                else:
                    period = "unknown"

            entity = _to_str(row.get("公司"))
            vals = [period, entity]
            for cn_name, en_name in COL_MAP.items():
                if en_name not in INSERT_COLUMNS[2:]:
                    continue
                val = row.get(cn_name)
                if en_name in NUMERIC_COLS:
                    vals.append(_to_num(val))
                elif en_name in INT_COLS:
                    vals.append(_to_int(val))
                elif en_name in DATE_COLS:
                    vals.append(_to_date(val))
                else:
                    vals.append(_to_str(val))

            batch.append(tuple(vals))

            if len(batch) >= batch_size:
                await conn.copy_records_to_table(
                    "income_margin_detail",
                    columns=INSERT_COLUMNS,
                    records=batch,
                )
                grand_total += len(batch)
                if grand_total % 20_000 == 0:
                    print(f"  {grand_total:,} inserted  [{time.time()-t2:.1f}s]")
                batch.clear()

        if batch:
            await conn.copy_records_to_table(
                "income_margin_detail",
                columns=INSERT_COLUMNS,
                records=batch,
            )
            grand_total += len(batch)

        print(f"  File done: {len(df):,} rows [{time.time()-t2:.1f}s]")

    if dry_run:
        print("\n=== DRY RUN complete ===")
        await conn.close()
        return

    # Verify
    count = await conn.fetchval("SELECT count(*) FROM income_margin_detail")
    periods = await conn.fetch(
        "SELECT period, count(*) as cnt FROM income_margin_detail "
        "GROUP BY period ORDER BY period"
    )
    print(f"\n=== Verification ===")
    print(f"Total rows: {count:,}")
    print(f"Periods ({len(periods)}):")
    for p in periods:
        print(f"  {p['period']}: {p['cnt']:,}")

    elapsed = time.time() - t0
    print(f"\nDone! {grand_total:,} inserted [{elapsed:.1f}s]")
    await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
