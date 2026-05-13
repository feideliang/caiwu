"""Add composite index on notification(user_id, created_at) for faster pagination.

Run: python scripts/migrate_notification_index.py
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
        # Check if index already exists
        exists = conn.execute(text("""
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'notification' AND indexname = 'ix_notification_user_created'
        """)).first()

        if exists:
            print("Index ix_notification_user_created already exists.", flush=True)
        else:
            print("Creating index ix_notification_user_created on notification(user_id, created_at DESC)...", flush=True)
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY ix_notification_user_created
                ON notification (user_id, created_at DESC)
            """))
            print("Done.", flush=True)

    engine.dispose()
    print("Migration complete.", flush=True)


if __name__ == "__main__":
    main()
