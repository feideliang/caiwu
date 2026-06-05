"""
分块导入 Excel -> income_margin_detail
pandas chunksize 流式读取，每块 10000 行
"""
import pandas as pd
import asyncpg
import asyncio
import time
from datetime import datetime, date
import math


FILE = r"D:\日志\05\21\收入毛利明细数据for驾驶舱_202510-202604.xlsx"
TABLE = "income_margin_detail"
CHUNK = 3000

# Excel 列名 -> 表列名
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

INSERT_COLS = [
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
]

INT_SET = {"order_qty", "revenue_qty", "revenue_year", "revenue_month"}
NUMERIC_SET = {
    "order_amount", "exchange_rate_local", "exchange_rate_rmb", "tax_rate",
    "revenue_amount", "revenue_amount_local", "revenue_amount_original",
    "cost_amount", "unit_cost_ex_tax", "gross_profit_amount", "gross_margin_pct",
    "cost_incl_tax", "unit_cost_incl_tax", "gross_profit_incl_tax",
    "sales_amount_incl_tax_local", "sales_amount_incl_tax_rmb",
    "sales_amount_incl_tax_original", "tax_amount_local",
}
DATE_SET = {"order_register_date", "revenue_confirm_date"}


def clean(val, col):
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if col in INT_SET:
        try:
            return int(val)
        except (ValueError, TypeError):
            return None
    if col in DATE_SET:
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        try:
            return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
        except:
            return None
    if col in NUMERIC_SET:
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    return str(val)


async def main():
    t0 = time.time()

    conn = await asyncpg.connect(
        "postgresql://learnhouse:learnhouse@localhost:5432/caiwu"
    )

    # 删除 >= 2025-10 的数据（幂等）
    r = await conn.execute(f"DELETE FROM {TABLE} WHERE period >= '2025-10'")
    print(f"Deleted: {r}")

    print(f"Reading {FILE}...")
    t1 = time.time()
    df = pd.read_excel(FILE, engine="openpyxl")
    print(f"  Read {len(df):,} rows [{time.time()-t1:.1f}s]")

    # rename columns
    df = df.rename(columns=COL_MAP)

    # compute period
    rcd = pd.to_datetime(df.get("revenue_confirm_date"), errors="coerce")
    df["period"] = rcd.dt.to_period("M").astype(str)
    mask = df["period"].isna() | (df["period"] == "NaT")
    if mask.any():
        df.loc[mask, "period"] = (
            df.loc[mask, "revenue_year"].astype(int).astype(str) + "-" +
            df.loc[mask, "revenue_month"].astype(int).astype(str).str.zfill(2)
        )

    # entity = company
    df["entity"] = df.get("company")

    # add missing columns
    for c in INSERT_COLS:
        if c not in df.columns:
            df[c] = None

    df = df[INSERT_COLS]

    print(f"Inserting in chunks of {CHUNK}...")
    t2 = time.time()
    total = 0

    for i in range(0, len(df), CHUNK):
        chunk = df.iloc[i:i+CHUNK]
        records = []
        for _, row in chunk.iterrows():
            vals = []
            for col in INSERT_COLS:
                vals.append(clean(row[col], col))
            records.append(tuple(vals))

        await conn.copy_records_to_table(TABLE, columns=INSERT_COLS, records=records)
        total += len(records)
        print(f"  {total:,} rows [{time.time()-t2:.1f}s]")

    # 验证
    cnt = await conn.fetchval(f"SELECT count(*) FROM {TABLE}")
    periods = await conn.fetch(f"SELECT period, count(*) as cnt FROM {TABLE} GROUP BY period ORDER BY period")
    print(f"\n=== Total: {cnt:,} ===")
    for p in periods:
        print(f"  {p['period']}: {p['cnt']:,}")

    await conn.close()
    print(f"\nDone! [{time.time()-t0:.1f}s]")


if __name__ == "__main__":
    asyncio.run(main())
