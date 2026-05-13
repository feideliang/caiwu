"""Add composite index on financial_data(period, metric_name) for faster core metrics queries.

The main query in metrics_service.py is:
  SELECT * FROM financial_data WHERE period IN (...)

This is then filtered in Python by metric_name. A composite index on (period, metric_name)
allows the DB to use an index-only scan for the IN list.

Run: python scripts/migrate_financial_data_index.py
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


def main():
    engine = create_engine(DB_URL, isolation_level="AUTOCOMMIT")

    with engine.connect() as conn:
        # Check existing indexes
        existing = conn.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'financial_data'
        """)).fetchall()
        existing_names = {r[0] for r in existing}
        print(f"Current indexes on financial_data: {existing_names}", flush=True)

        if 'ix_financial_data_period_metric' not in existing_names:
            print("Creating index ix_financial_data_period_metric on financial_data(period, metric_name)...", flush=True)
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY ix_financial_data_period_metric
                ON financial_data (period, metric_name)
            """))
            print("Done.", flush=True)
        else:
            print("Index already exists.", flush=True)

    engine.dispose()
    print("Migration complete.", flush=True)


if __name__ == "__main__":
    main()
