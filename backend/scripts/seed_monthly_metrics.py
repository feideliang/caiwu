"""Seed 12 months of summary metric data (revenue/cost/gross_profit/profit_margin/achievement_rate)
for all entities to support MoM, YoY, cumulative, and trend chart analysis.

Generates data for 2025-07 through 2026-06 (12 months).
Uses random seed for reproducibility.
"""
import os
import sys
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "caiwu")
DB_USER = os.getenv("DB_USER", "learnhouse")
DB_PASSWORD = os.getenv("DB_PASSWORD", "learnhouse")

DB_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 12 months: 2025-07 to 2026-06
PERIODS = [
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
]

# Metrics to generate per entity per period
METRICS = ["revenue", "cost", "gross_profit", "profit_margin", "achievement_rate"]

# Base revenue ranges per entity (monthly, in CNY)
# These are realistic B2B tech company department monthly revenues
ENTITY_BASE = {
    "CBG": (1_500_000, 3_000_000),
    "EBG": (2_000_000, 4_000_000),
    "SBG": (1_000_000, 2_500_000),
    "TBU": (800_000, 1_800_000),
    "DEFAULT": (500_000, 1_200_000),
    # Chinese-named entities
    "企业网络产品事业部": (1_200_000, 2_800_000),
    "企业无线产品事业部": (1_000_000, 2_500_000),
    "运营商事业部": (1_500_000, 3_500_000),
    "海外业务部": (800_000, 2_000_000),
    "战略和业务发展部": (600_000, 1_500_000),
    "服务与软件事业部": (1_000_000, 2_200_000),
}


def main():
    rng = random.Random(123)
    engine = create_engine(DB_URL)

    with engine.connect() as conn:
        # Get existing entities from DB
        rows = conn.execute(
            text("SELECT DISTINCT entity FROM financial_data WHERE entity IS NOT NULL ORDER BY entity")
        ).fetchall()
        entities = [r[0] for r in rows]

        if not entities:
            print("ERROR: No entities found in financial_data. Run seed_data.py first.")
            return

        print(f"Found {len(entities)} entities")

        # Check existing data
        existing = conn.execute(
            text("SELECT period, count(*) FROM financial_data WHERE period != '2026-03' GROUP BY period ORDER BY period")
        ).fetchall()
        if existing:
            print(f"WARNING: Non-2026-03 data already exists:")
            for period, cnt in existing:
                print(f"  {period}: {cnt} rows")
            resp = input("Continue anyway? (y/N): ")
            if resp.lower() != 'y':
                print("Aborted.")
                return

        total_inserted = 0

        for period in PERIODS:
            if period == "2026-03":
                # Already has 30600 rows, skip
                print(f"Period {period}: already exists, skipping")
                continue

            for entity in entities:
                base_lo, base_hi = ENTITY_BASE.get(entity, (500_000, 1_500_000))

                # Add some seasonal variation (Q4 typically higher for B2B)
                month = int(period.split("-")[1])
                seasonal = 1.0
                if month in (10, 11, 12):
                    seasonal = rng.uniform(1.1, 1.3)
                elif month in (1, 2):
                    seasonal = rng.uniform(0.7, 0.9)  # Chinese New Year dip

                # Generate base revenue for this entity+month
                revenue = round(rng.uniform(base_lo, base_hi) * seasonal, 2)

                # Cost: 55-75% of revenue
                cost_ratio = rng.uniform(0.55, 0.75)
                cost = round(revenue * cost_ratio, 2)

                # Gross profit
                gross_profit = round(revenue - cost, 2)

                # Profit margin percentage
                profit_margin = round((gross_profit / revenue) * 100, 2) if revenue > 0 else 0

                # Achievement rate: 80-120%
                achievement_rate = round(rng.uniform(80, 120), 2)

                metrics = {
                    "revenue": revenue,
                    "cost": cost,
                    "gross_profit": gross_profit,
                    "profit_margin": profit_margin,
                    "achievement_rate": achievement_rate,
                }

                for metric_name, metric_value in metrics.items():
                    conn.execute(
                        text("""
                            INSERT INTO financial_data
                                (batch_id, metric_name, metric_value, metric_unit, period, entity, tags, raw_row)
                            VALUES
                                (NULL, :metric, :val, 'CNY', :period, :entity, NULL, NULL)
                        """),
                        {
                            "metric": metric_name,
                            "val": metric_value,
                            "period": period,
                            "entity": entity,
                        },
                    )
                    total_inserted += 1

            print(f"Period {period}: seeded 5 metrics x {len(entities)} entities = {5 * len(entities)} rows")

        conn.commit()
        print(f"\nDone. Total rows inserted: {total_inserted}")

        # Verify
        r = conn.execute(text("SELECT period, count(*) FROM financial_data GROUP BY period ORDER BY period"))
        print("\nPeriod distribution after seeding:")
        for row in r:
            print(f"  {row[0]}: {row[1]} rows")

    engine.dispose()


if __name__ == "__main__":
    main()
