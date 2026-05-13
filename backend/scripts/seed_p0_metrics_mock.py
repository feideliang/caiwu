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
    "2025-04", "2025-05", "2025-06",
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

# Period -> base revenue, with MoM growth so trend-up fires
PERIOD_BASE_REVENUE = {
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
                        tags_json = json.dumps({
                            "customer": customer_name,
                            "customer_name": customer_name,
                            "product_line": product_name,
                            "product": product_name,
                            "order_id": order_id,
                            "contract_no": contract_no,
                            "department": department,
                            "bu": DEPT_TO_BU.get(department, department),
                            "region": region,
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
