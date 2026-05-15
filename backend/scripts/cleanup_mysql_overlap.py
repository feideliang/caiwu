"""Remove overlapping MySQL data that conflicts with mock data.

The mock seed covers 2024-01 through 2026-06.
MySQL import covers 2025-07 through 2025-12 (overlap with mock).
Delete MySQL rows for overlapping periods so BFF returns correct values.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

db_user = os.getenv('DB_USER', 'learnhouse')
db_pass = os.getenv('DB_PASSWORD', 'learnhouse')
db_host = os.getenv('DB_HOST', 'localhost')
db_port = os.getenv('DB_PORT', '5432')
db_name = os.getenv('DB_NAME', 'caiwu')
DB_URL = f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

engine = create_engine(DB_URL)

with engine.begin() as conn:
    # Delete all rows where raw_row->>'mock_source' IS NULL (mysql-imported)
    result = conn.execute(text(
        "DELETE FROM financial_data WHERE raw_row->>'mock_source' IS NULL"
    ))
    print(f"Deleted {result.rowcount} MySQL-imported rows (no mock_source tag)")

    # Verify remaining data
    r = conn.execute(text(
        "SELECT COUNT(*) FROM financial_data WHERE raw_row->>'mock_source' IS NOT NULL"
    ))
    print(f"Remaining mock rows: {r.scalar()}")

engine.dispose()