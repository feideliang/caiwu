"""
Fast import: Excel -> income_margin_detail (or test table).
Uses vectorized pandas ops + asyncpg COPY.
"""
import asyncio, time, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import pandas as pd
import asyncpg

FILE = Path(r"D:\日志\05\21\收入毛利明细数据for驾驶舱_202510-202604.xlsx")

# Chinese -> English column map
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
    "产品所属事业部": "product_bgbu",
    "产品所属组织": "product_org",
    "产品系列": "series",
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

# Target table columns in order
INSERT_COLS = [
    "period", "entity",
    "order_register_date", "revenue_confirm_date",
    "order_id", "contract_no", "order_category", "order_header_type",
    "order_customer", "sequence_no", "order_amount", "order_qty",
    "company", "hr_dept_code", "hr_department", "sales_department",
    "sales_person_code", "sales_person",
    "product_category", "product_classification", "product_bu_code",
    "product_bu_name", "product_bgbu", "product_org", "series",
    "product_family", "sales_product_code", "sales_product_name",
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
]

TARGET_TABLE = "income_margin_detail"
NROWS = None  # all rows


async def main():
    t0 = time.time()
    db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

    # Read Excel
    print(f"Reading {FILE.name}...")
    df = pd.read_excel(FILE, nrows=NROWS, engine="openpyxl")
    print(f"  {len(df):,} rows, {len(df.columns)} cols [{time.time()-t0:.1f}s]")

    # Rename columns
    df = df.rename(columns=COL_MAP)

    # Derive period
    t1 = time.time()
    rcd = pd.to_datetime(df.get("revenue_confirm_date"), errors="coerce")
    df["period"] = rcd.dt.to_period("M").astype(str)
    # Fallback: use revenue_year + revenue_month
    mask = df["period"].isna() | (df["period"] == "NaT")
    if mask.any():
        df.loc[mask, "period"] = (
            df.loc[mask, "revenue_year"].astype(int).astype(str) + "-" +
            df.loc[mask, "revenue_month"].astype(int).astype(str).str.zfill(2)
        )

    # Entity = company
    df["entity"] = df.get("company")

    # product_bgbu should use 产品事业部名称 when 产品所属事业部 is absent/blank
    if "product_bgbu" in df.columns and "product_bu_name" in df.columns:
        df["product_bgbu"] = df["product_bgbu"].where(df["product_bgbu"].notna(), df["product_bu_name"])

    # Keep only insert columns
    missing = [c for c in INSERT_COLS if c not in df.columns]
    if missing:
        for c in missing:
            df[c] = None
    df = df[INSERT_COLS]

    # Convert dates
    for col in ["order_register_date", "revenue_confirm_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    # Integer columns - keep as float, convert in clean step
    for col in ["order_qty", "revenue_qty", "revenue_year", "revenue_month"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Numeric columns
    numeric_cols = [
        "order_amount", "exchange_rate_local", "exchange_rate_rmb", "tax_rate",
        "revenue_amount", "revenue_amount_local", "revenue_amount_original",
        "cost_amount", "unit_cost_ex_tax", "gross_profit_amount", "gross_margin_pct",
        "cost_incl_tax", "unit_cost_incl_tax", "gross_profit_incl_tax",
        "sales_amount_incl_tax_local", "sales_amount_incl_tax_rmb",
        "sales_amount_incl_tax_original", "tax_amount_local",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # All other columns -> string
    str_cols = set(INSERT_COLS) - set(numeric_cols) - {"order_qty", "revenue_qty", "revenue_year", "revenue_month"} - {"order_register_date", "revenue_confirm_date"} - {"period", "entity"}
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: str(x) if x is not None and not (isinstance(x, float) and pd.isna(x)) else None)

    # Replace NaN/NaT with None
    df = df.where(df.notna(), None)

    # Convert to list of tuples, handling None properly
    print(f"  Converting... [{time.time()-t1:.1f}s]")
    INT_SET = {"order_qty", "revenue_qty", "revenue_year", "revenue_month"}
    col_names = list(df.columns)
    int_indices = {i for i, c in enumerate(col_names) if c in INT_SET}

    def clean(val, is_int=False):
        if val is None:
            return None
        if isinstance(val, float) and pd.isna(val):
            return None
        if is_int:
            try:
                return int(val)
            except (ValueError, TypeError):
                return None
        return val

    records = []
    for row in df.itertuples(index=False, name=None):
        records.append(tuple(clean(v, i in int_indices) for i, v in enumerate(row)))
    print(f"  {len(records):,} records [{time.time()-t1:.1f}s]")

    # Insert
    conn = await asyncpg.connect(db_url)

    if TARGET_TABLE == "income_margin_test":
        print(f"\nTruncating test table...")
        await conn.execute("TRUNCATE income_margin_test")
    elif TARGET_TABLE == "income_margin_detail":
        print(f"\nDeleting existing rows >= 2025-10...")
        r = await conn.execute("DELETE FROM income_margin_detail WHERE period >= '2025-10'")
        print(f"  {r}")

    print(f"\nInserting {len(records):,} rows into {TARGET_TABLE}...")
    t2 = time.time()

    batch_size = 10_000
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        await conn.copy_records_to_table(TARGET_TABLE, columns=INSERT_COLS, records=batch)
        total += len(batch)
        print(f"  {total:,}/{len(records):,} [{time.time()-t2:.1f}s]")

    # Verify
    count = await conn.fetchval(f"SELECT count(*) FROM {TARGET_TABLE}")
    periods = await conn.fetch(
        f"SELECT period, count(*) as cnt FROM {TARGET_TABLE} GROUP BY period ORDER BY period"
    )
    print(f"\n=== Verification ===")
    print(f"Total: {count:,}")
    for p in periods:
        print(f"  {p['period']}: {p['cnt']:,}")

    await conn.close()
    print(f"\nDone! [{time.time()-t0:.1f}s]")


if __name__ == "__main__":
    asyncio.run(main())
