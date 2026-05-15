"""Seed mock data for P0.2 metrics & P0.3 insight rules.

Inserts financial_data rows with rich tags to enable:
- Customer concentration rule (single customer > 30% revenue)
- Product concentration rule (single product_line > 40% gross_profit)
- High-margin order ratio (order-level rev/cost/gp via tags.order_id)
- Trend-up rules (consecutive MoM positive in last 3 months)
- Multi-dimension breakdowns (customer / product_line / order_id / department)

Idempotent: deletes prior mock rows (tagged with mock_source=p0_metrics) before re-seeding.
"""

import os
import sys
import json
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_URL = (
    f"postgresql+psycopg://"
    f"{os.getenv('DB_USER','learnhouse')}:{os.getenv('DB_PASSWORD','learnhouse')}"
    f"@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}"
    f"/{os.getenv('DB_NAME','caiwu')}"
)

MOCK_TAG = "p0_metrics"

PERIODS = [
    "2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06",
    "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12",
    "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
]

# Customer mix designed so the largest customer takes ~35% of 2026-03 revenue
CUSTOMERS = [
    ("华为科技", 0.35),
    ("阿里云", 0.18),
    ("腾讯", 0.14),
    ("中国移动", 0.10),
    ("字节跳动", 0.08),
    ("百度", 0.06),
    ("京东", 0.05),
    ("美团", 0.04),
]

# Product lines — top line takes ~45% of gross profit
PRODUCT_LINES = [
    ("企业网络", 0.45),
    ("无线产品", 0.20),
    ("数据中心交换机", 0.15),
    ("安全产品", 0.10),
    ("云服务", 0.06),
    ("软件订阅", 0.04),
]

DEPARTMENTS = ["CBG", "EBG", "SBG", "TBU"]
# BU (business unit) — higher-level grouping above department
DEPT_TO_BU = {
    "CBG": "消费者BG",
    "EBG": "企业BG",
    "SBG": "运营商BG",
    "TBU": "技术BU",
}
REGIONS = ["华东", "华南", "华北", "西南", "海外"]

# Contract types for customer segmentation
CONTRACT_TYPES = ["直签", "代理", "经销"]
CONTRACT_TYPE_WEIGHTS = [0.30, 0.40, 0.30]  # 30% 直签, 40% 代理, 30% 经销

# Market segments (细分市场)
MARKET_SEGMENTS = [
    "企业网络", "无线产品", "数据中心交换机", "安全产品",
    "云服务", "软件订阅", "智能终端", "物联网"
]

# Customer -> superior_name mapping (上级客户名称)
CUSTOMER_SUPERIOR = {
    "华为科技": "华为集团",
    "阿里云": "阿里巴巴集团",
    "腾讯": "腾讯集团",
    "中国移动": "中国移动通信集团",
    "字节跳动": "字节跳动集团",
    "百度": "百度集团",
    "京东": "京东集团",
    "美团": "美团集团",
}

# Order categories
ORDER_CATEGORIES = ["标准订单", "项目订单", "框架订单", "定制订单"]

# Sales types
SALES_TYPES = ["内销", "外销"]

# Product drill-down: sales_product_name per product_line
PRODUCT_MODEL_CODES = {
    "企业网络": ["EN3000", "EN5000", "EN7000"],
    "无线产品": ["WP2000", "WP4000", "WP6000"],
    "数据中心交换机": ["DC1000", "DC3000", "DC5000"],
    "安全产品": ["SP2000", "SP4000", "SP6000"],
    "云服务": ["CS100", "CS200", "CS300"],
    "软件订阅": ["SS100", "SS200", "SS300"],
}

# Province mapping
REGION_PROVINCE = {"华东": "江苏", "华南": "广东", "华北": "北京", "西南": "四川", "海外": "海外"}

# Sales department mapping
DEPT_SALES_DEPT = {
    "CBG": "CBG销售一部",
    "EBG": "EBG企业销售部",
    "SBG": "SBG运营商销售部",
    "TBU": "TBU技术销售部",
}

# HR department mapping
DEPT_HR_DEPT = {
    "CBG": "消费者业务部",
    "EBG": "企业业务部",
    "SBG": "运营商业务部",
    "TBU": "技术事业部",
}

# Sales person pool
SALES_PEOPLE = [
    ("张伟", "SP001"), ("李明", "SP002"), ("王芳", "SP003"),
    ("刘洋", "SP004"), ("陈静", "SP005"), ("杨帆", "SP006"),
    ("赵磊", "SP007"), ("周婷", "SP008"), ("吴强", "SP009"),
    ("郑敏", "SP010"), ("孙浩", "SP011"), ("马丽", "SP012"),
]

# Cost classifications
COST_CLASS_1 = ["直接材料", "人工成本", "制造费用"]
COST_CLASS_2 = ["原材料", "元器件", "软件授权", "加工费", "人工工资", "折旧摊销"]
COST_CLASS_3 = ["芯片", "PCB", "光模块", "电源模块", "机箱", "散热器"]

# Material codes per product line
MATERIAL_PREFIXES = {
    "企业网络": "EN-MAT",
    "无线产品": "WP-MAT",
    "数据中心交换机": "DC-MAT",
    "安全产品": "SP-MAT",
    "云服务": "CS-MAT",
    "软件订阅": "SS-MAT",
}

# Product categories & classifications
PRODUCT_CATEGORIES = {
    "企业网络": "网络设备",
    "无线产品": "通信设备",
    "数据中心交换机": "数据中心设备",
    "安全产品": "安全设备",
    "云服务": "云服务",
    "软件订阅": "软件服务",
}
PRODUCT_CLASSIFICATIONS = ["高端", "中端", "低端"]

# NCC customer codes
NCC_CODES = {
    "华为科技": "NCC-HW001",
    "阿里云": "NCC-AL001",
    "腾讯": "NCC-TX001",
    "中国移动": "NCC-YD001",
    "字节跳动": "NCC-BD001",
    "百度": "NCC-BD001",
    "京东": "NCC-JD001",
    "美团": "NCC-MT001",
}

# Order header types
ORDER_HEADER_TYPES = ["标准订单", "退货订单", "赠品订单"]

# Period -> base revenue, with MoM growth so trend-up fires
PERIOD_BASE_REVENUE = {
    "2024-01": 4_100_000.0,
    "2024-02": 4_200_000.0,
    "2024-03": 4_400_000.0,
    "2024-04": 4_500_000.0,
    "2024-05": 4_600_000.0,
    "2024-06": 4_800_000.0,
    "2024-07": 4_700_000.0,
    "2024-08": 4_500_000.0,
    "2024-09": 5_100_000.0,
    "2024-10": 5_400_000.0,
    "2024-11": 5_700_000.0,
    "2024-12": 6_000_000.0,
    "2025-01": 5_800_000.0,
    "2025-02": 6_000_000.0,
    "2025-03": 6_300_000.0,
    "2025-04": 5_800_000.0,
    "2025-05": 6_100_000.0,
    "2025-06": 6_500_000.0,
    "2025-07": 6_800_000.0,
    "2025-08": 6_300_000.0,
    "2025-09": 7_000_000.0,
    "2025-10": 7_800_000.0,
    "2025-11": 8_200_000.0,
    "2025-12": 8_600_000.0,
    "2026-01": 8_000_000.0,
    "2026-02": 9_200_000.0,
    "2026-03": 11_000_000.0,
    "2026-04": 10_500_000.0,
    "2026-05": 11_400_000.0,
    "2026-06": 12_100_000.0,
}


def main():
    rng = random.Random(2026)
    engine = create_engine(DB_URL)

    with engine.begin() as conn:
        deleted = conn.execute(
            text("DELETE FROM financial_data WHERE raw_row->>'mock_source' = :tag"),
            {"tag": MOCK_TAG},
        ).rowcount
        print(f"Cleaned {deleted} prior mock rows", flush=True)

        batch_rows: list[dict] = []
        for period in PERIODS:
            base_revenue = PERIOD_BASE_REVENUE[period]

            num_orders = 80
            order_idx = 0
            period_total_revenue = 0.0

            for customer_name, cust_share in CUSTOMERS:
                cust_revenue_target = base_revenue * cust_share
                for product_name, prod_share in PRODUCT_LINES:
                    if order_idx >= num_orders:
                        break
                    n_orders = rng.randint(1, 2)
                    for _ in range(n_orders):
                        order_idx += 1
                        order_id = f"ORD-{period.replace('-','')}-{order_idx:04d}"
                        order_revenue = round(
                            cust_revenue_target * prod_share * rng.uniform(0.6, 1.4) / n_orders, 2
                        )
                        if order_revenue <= 0:
                            continue
                        period_total_revenue += order_revenue

                        if rng.random() < 0.28:
                            margin = rng.uniform(0.42, 0.60)
                        else:
                            margin = rng.uniform(0.10, 0.35)
                        order_cost = round(order_revenue * (1 - margin), 2)
                        order_gp = round(order_revenue - order_cost, 2)

                        department = rng.choice(DEPARTMENTS)
                        region = rng.choice(REGIONS)
                        contract_no = f"CT-{period.replace('-','')}-{order_idx:04d}"
                        contract_type = rng.choices(CONTRACT_TYPES, weights=CONTRACT_TYPE_WEIGHTS, k=1)[0]
                        market_segment = rng.choice(MARKET_SEGMENTS)
                        order_category = rng.choice(ORDER_CATEGORIES)
                        sales_type = rng.choices(SALES_TYPES, weights=[0.85, 0.15], k=1)[0]

                        # Expanded fields for 64-tag coverage
                        model_code = rng.choice(PRODUCT_MODEL_CODES.get(product_name, ["MOD-001"]))
                        sales_product_name = f"{product_name}-{model_code}"
                        sales_product_code = f"SPC-{model_code}"
                        province = REGION_PROVINCE.get(region, region)
                        sales_dept = DEPT_SALES_DEPT.get(department, department)
                        hr_dept = DEPT_HR_DEPT.get(department, department)
                        hr_dept_code = f"HR-{department}-001"
                        sales_person, sales_person_code = rng.choice(SALES_PEOPLE)
                        superior = CUSTOMER_SUPERIOR.get(customer_name, customer_name)
                        final_customer = superior
                        order_customer = customer_name
                        invoice_customer = f"{customer_name}(开票)"
                        invoice_name = f"{customer_name}开票名称"
                        ncc_code = NCC_CODES.get(customer_name, "NCC-GEN001")
                        order_header_type = rng.choice(ORDER_HEADER_TYPES)
                        material_prefix = MATERIAL_PREFIXES.get(product_name, "MAT-GEN")
                        material_code = f"{material_prefix}-{rng.randint(100,999)}"
                        material_desc = f"{product_name}配件{rng.randint(1,9)}"
                        product_category = PRODUCT_CATEGORIES.get(product_name, "通用产品")
                        product_classification = rng.choice(PRODUCT_CLASSIFICATIONS)
                        product_family = f"{product_name}系列"
                        cost_c1 = rng.choice(COST_CLASS_1)
                        cost_c2 = rng.choice(COST_CLASS_2)
                        cost_c3 = rng.choice(COST_CLASS_3)
                        cost_category = cost_c1
                        order_qty = rng.randint(1, 50)
                        revenue_qty = order_qty
                        tax_rate = rng.choice([0.06, 0.09, 0.13, 0.16])
                        unit_cost_ex_tax = round(order_cost / max(order_qty, 1), 2)
                        unit_cost_incl_tax = round(unit_cost_ex_tax * (1 + tax_rate), 2)
                        currency = "CNY"

                        tags_json = json.dumps({
                            # Existing tags (14)
                            "customer": customer_name,
                            "customer_name": customer_name,
                            "product_line": product_name,
                            "product": product_name,
                            "order_id": order_id,
                            "contract_no": contract_no,
                            "department": department,
                            "bu": DEPT_TO_BU.get(department, department),
                            "region": region,
                            "contract_type": contract_type,
                            "market_segment": market_segment,
                            "order_category": order_category,
                            "sales_type": sales_type,
                            "superior_name": superior,
                            # Product dimension (drill-down)
                            "sales_product_name": sales_product_name,
                            "sales_product_code": sales_product_code,
                            "product_category": product_category,
                            "product_classification": product_classification,
                            "product_family": product_family,
                            "material_code": material_code,
                            "material_desc": material_desc,
                            "material_cost_category": cost_c1,
                            # Customer dimension
                            "final_customer": final_customer,
                            "order_customer": order_customer,
                            "invoice_customer": invoice_customer,
                            "invoice_name": invoice_name,
                            "ncc_customer_code": ncc_code,
                            # Department / region
                            "sales_department": sales_dept,
                            "hr_department": hr_dept,
                            "hr_dept_code": hr_dept_code,
                            "province": province,
                            "sales_person": sales_person,
                            "sales_person_code": sales_person_code,
                            # Cost classification
                            "cost_class_1": cost_c1,
                            "cost_class_2": cost_c2,
                            "cost_class_3": cost_c3,
                            "cost_category": cost_category,
                            # Financial detail
                            "order_qty": order_qty,
                            "revenue_qty": revenue_qty,
                            "unit_cost_ex_tax": unit_cost_ex_tax,
                            "unit_cost_incl_tax": unit_cost_incl_tax,
                            "tax_rate": tax_rate,
                            "currency": currency,
                            "order_header_type": order_header_type,
                        }, ensure_ascii=False)
                        raw_json = json.dumps(
                            {"mock_source": MOCK_TAG, "order_id": order_id},
                            ensure_ascii=False,
                        )

                        for metric_name, metric_value in (
                            ("revenue", order_revenue),
                            ("cost", order_cost),
                            ("gross_profit", order_gp),
                        ):
                            batch_rows.append({
                                "m": metric_name,
                                "v": metric_value,
                                "p": period,
                                "e": department,
                                "tags": tags_json,
                                "raw": raw_json,
                            })

            print(f"Period {period}: prepared {order_idx} orders, revenue ~ {period_total_revenue:,.0f}", flush=True)

        print(f"Bulk inserting {len(batch_rows)} rows...", flush=True)
        conn.execute(
            text("""
                INSERT INTO financial_data
                    (batch_id, metric_name, metric_value, metric_unit,
                     period, entity, tags, raw_row)
                VALUES
                    (NULL, :m, :v, 'CNY', :p, :e,
                     CAST(:tags AS JSON), CAST(:raw AS JSON))
            """),
            batch_rows,
        )
        print(f"Done. Inserted {len(batch_rows)} rows.", flush=True)

    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT period, count(*)
            FROM financial_data
            WHERE raw_row->>'mock_source' = :tag
            GROUP BY period ORDER BY period
        """), {"tag": MOCK_TAG})
        print("\nMock data by period:", flush=True)
        for p, n in r:
            print(f"  {p}: {n} rows", flush=True)

    engine.dispose()


if __name__ == "__main__":
    main()
