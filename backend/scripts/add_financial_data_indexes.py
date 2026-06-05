"""Add performance indexes to financial_data table.

Creates composite and GIN indexes to speed up the most common queries:
- Dashboard BFF: period + metric_name aggregation
- Core metrics: period + metric_name filtering
- Dimension breakdowns: tags JSON queries (department, product_bgbu, customer)
"""

import os
import sys

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

INDEXES = [
    # Composite index for period + metric_name queries (dashboard BFF, core metrics)
    (
        "idx_financial_data_period_metric",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_financial_data_period_metric "
        "ON financial_data (period, metric_name)",
    ),
    # Composite index for period + entity filtering (dimension breakdowns)
    (
        "idx_financial_data_period_entity",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_financial_data_period_entity "
        "ON financial_data (period, entity)",
    ),
    # Expression indexes on tags JSON keys for dimension queries
    (
        "idx_financial_data_tags_department",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_financial_data_tags_department "
        "ON financial_data ((tags->>'department'))",
    ),
    (
        "idx_financial_data_tags_product_bgbu",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_financial_data_tags_product_bgbu "
        "ON financial_data ((tags->>'product_bgbu'))",
    ),
    (
        "idx_financial_data_tags_customer",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_financial_data_tags_customer "
        "ON financial_data ((tags->>'customer'))",
    ),
    # Composite index for metric_name + period (reverse lookup for trend series)
    (
        "idx_financial_data_metric_period",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_financial_data_metric_period "
        "ON financial_data (metric_name, period)",
    ),
    # Index on batch_id for join queries
    (
        "idx_financial_data_batch_id",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_financial_data_batch_id "
        "ON financial_data (batch_id)",
    ),
]


def main():
    engine = create_engine(DB_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        for name, ddl in INDEXES:
            # Check if index already exists
            check = conn.execute(text("""
                SELECT 1 FROM pg_indexes WHERE indexname = :name
            """), {"name": name}).scalar()
            if check:
                print(f"  SKIP: index {name} already exists")
                continue
            print(f"  Creating {name}...")
            conn.execute(text(ddl))
            print(f"  Done: {name}")

        # Verify
        print("\nIndexes on financial_data:")
        rows = conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'financial_data'
            ORDER BY indexname
        """)).fetchall()
        for r in rows:
            print(f"  {r[0]}")

    engine.dispose()
    print("\nIndex optimization complete.")


if __name__ == "__main__":
    main()
