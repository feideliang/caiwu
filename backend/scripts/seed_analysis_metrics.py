"""Seed analysis-specific metrics that are missing from financial_data.

Adds metric_name records for:
- target_revenue: revenue target per department per period (for achievement_rate)
- order_count: total order count per period (company-level)
- loss_count / total_count: loss-making order counts per product_line per period

Idempotent: deletes prior rows with raw_row->>'mock_source' = 'analysis_metrics' before re-seeding.
Does NOT TRUNCATE financial_data.
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

MOCK_TAG = "analysis_metrics"

PERIODS = [
    "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
]

DEPARTMENTS = ["CBG", "EBG", "SBG", "TBU"]
PRODUCT_LINES = ["企业网络", "无线产品", "数据中心交换机", "安全产品", "云服务", "软件订阅"]

# Department revenue share (for target calculation)
DEPT_SHARE = {"CBG": 0.35, "EBG": 0.28, "SBG": 0.22, "TBU": 0.15}

# Product line loss ratio (some products have more loss-making orders)
PRODUCT_LOSS_RATE = {
    "企业网络": 0.03,
    "无线产品": 0.06,
    "数据中心交换机": 0.02,
    "安全产品": 0.08,
    "云服务": 0.12,
    "软件订阅": 0.05,
}


def main():
    rng = random.Random(2026)
    engine = create_engine(DB_URL, isolation_level="AUTOCOMMIT")

    with engine.connect() as conn:
        # Clean prior mock rows
        deleted = conn.execute(
            text("DELETE FROM financial_data WHERE raw_row->>'mock_source' = :tag"),
            {"tag": MOCK_TAG},
        ).rowcount
        print(f"Cleaned {deleted} prior analysis_metrics rows", flush=True)

        batch_rows = []

        # 1. target_revenue per department per period
        # Fetch actual revenue per department per period to set realistic targets
        dept_rev_rows = conn.execute(text("""
            SELECT period, tags->>'department' as dept, SUM(metric_value) as rev
            FROM financial_data
            WHERE metric_name ILIKE '%revenue%' OR metric_name ILIKE '%营业收入%'
              AND tags->>'department' IS NOT NULL
            GROUP BY period, tags->>'department'
        """)).fetchall()

        dept_rev_map = {}
        for row in dept_rev_rows:
            period, dept, rev = row[0], row[1], float(row[2])
            dept_rev_map.setdefault(period, {})[dept] = rev

        for period in PERIODS:
            dept_data = dept_rev_map.get(period, {})
            for dept, share in DEPT_SHARE.items():
                actual_rev = dept_data.get(dept, 0)
                if actual_rev > 0:
                    target = actual_rev * 1.15  # 15% above actual
                else:
                    base = 300_000 * share
                    target = base * (1 + rng.uniform(-0.1, 0.2))

                batch_rows.append({
                    "metric_name": "target_revenue",
                    "metric_value": round(target, 2),
                    "metric_unit": "CNY",
                    "period": period,
                    "entity": dept,
                    "tags_val": json.dumps({"department": dept}),
                    "raw_row_val": json.dumps({"mock_source": MOCK_TAG, "note": f"{dept} target for {period}"}),
                })

        # 2. company-level target_revenue
        for period in PERIODS:
            total_actual = sum(dept_rev_map.get(period, {}).values())
            if total_actual > 0:
                target = total_actual * 1.12
            else:
                target = 10_000_000 * (1 + rng.uniform(-0.1, 0.2))

            batch_rows.append({
                "metric_name": "target_revenue",
                "metric_value": round(target, 2),
                "metric_unit": "CNY",
                "period": period,
                "entity": "company",
                "tags_val": json.dumps({}),
                "raw_row_val": json.dumps({"mock_source": MOCK_TAG, "note": f"company target for {period}"}),
            })

        # 3. order_count per period (based on actual order_id count or mock)
        actual_order_rows = conn.execute(text("""
            SELECT period, COUNT(DISTINCT tags->>'order_id') as cnt
            FROM financial_data
            WHERE tags->>'order_id' IS NOT NULL
            GROUP BY period
        """)).fetchall()

        order_count_map = {r[0]: int(r[1]) for r in actual_order_rows}

        for period in PERIODS:
            cnt = order_count_map.get(period, 0)
            if cnt == 0:
                cnt = rng.randint(60, 100)

            batch_rows.append({
                "metric_name": "order_count",
                "metric_value": float(cnt),
                "metric_unit": "count",
                "period": period,
                "entity": "company",
                "tags_val": json.dumps({}),
                "raw_row_val": json.dumps({"mock_source": MOCK_TAG, "note": f"order count for {period}"}),
            })

        # 4. loss_count and total_count per product_line per period
        for period in PERIODS:
            for product, loss_rate in PRODUCT_LOSS_RATE.items():
                total_orders = rng.randint(8, 20)
                loss_orders = max(0, int(total_orders * loss_rate + rng.uniform(-1, 1)))

                batch_rows.append({
                    "metric_name": "loss_count",
                    "metric_value": float(loss_orders),
                    "metric_unit": "count",
                    "period": period,
                    "entity": product,
                    "tags_val": json.dumps({"product_line": product}),
                    "raw_row_val": json.dumps({"mock_source": MOCK_TAG, "note": f"{product} loss count for {period}"}),
                })

                batch_rows.append({
                    "metric_name": "total_count",
                    "metric_value": float(total_orders),
                    "metric_unit": "count",
                    "period": period,
                    "entity": product,
                    "tags_val": json.dumps({"product_line": product}),
                    "raw_row_val": json.dumps({"mock_source": MOCK_TAG, "note": f"{product} total count for {period}"}),
                })

        # Bulk insert
        print(f"Inserting {len(batch_rows)} analysis metrics rows...", flush=True)
        for row_data in batch_rows:
            conn.execute(text("""
                INSERT INTO financial_data
                    (metric_name, metric_value, metric_unit, period, entity, tags, raw_row)
                VALUES
                    (:metric_name, :metric_value, :metric_unit, :period, :entity,
                     CAST(:tags_val AS json), CAST(:raw_row_val AS json))
            """), row_data)
        print(f"Done. Inserted {len(batch_rows)} rows.", flush=True)

        # Summary
        summary = conn.execute(text("""
            SELECT period, metric_name, COUNT(*) as cnt
            FROM financial_data
            WHERE raw_row->>'mock_source' = :tag
            GROUP BY period, metric_name
            ORDER BY period, metric_name
        """), {"tag": MOCK_TAG}).fetchall()

        print("\nMock data by period and metric:", flush=True)
        for row in summary:
            print(f"  {row[0]}: {row[1]} = {row[2]} rows", flush=True)

    engine.dispose()
    print("\nAnalysis metrics seeding complete.", flush=True)


if __name__ == "__main__":
    main()
