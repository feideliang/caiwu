"""Check what data exists in financial_data by source."""
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

with engine.connect() as conn:
    # Revenue rows by source for 2025
    q1 = """
    SELECT period,
        CASE WHEN raw_row->>'mock_source' IS NOT NULL THEN 'mock' ELSE 'mysql' END as source,
        COUNT(*) as cnt,
        SUM(metric_value) as total_val
    FROM financial_data
    WHERE metric_name = 'revenue' AND period LIKE '2025-%'
    GROUP BY period,
        CASE WHEN raw_row->>'mock_source' IS NOT NULL THEN 'mock' ELSE 'mysql' END
    ORDER BY period, source
    """
    r = conn.execute(text(q1))
    print("=== Revenue by source (2025) ===")
    for row in r:
        print(f"  {row[0]} | {row[1]} | count={row[2]} | sum={row[3]:,.0f}")

    # Total by source across all data
    q2 = """
    SELECT CASE WHEN raw_row->>'mock_source' IS NOT NULL THEN 'mock' ELSE 'mysql' END as source,
        COUNT(*) as cnt,
        SUM(CASE WHEN metric_name='revenue' THEN metric_value ELSE 0 END) as total_rev
    FROM financial_data
    GROUP BY CASE WHEN raw_row->>'mock_source' IS NOT NULL THEN 'mock' ELSE 'mysql' END
    """
    r2 = conn.execute(text(q2))
    print("\n=== Total by source ===")
    for row in r2:
        print(f"  {row[0]} | count={row[1]} | total_rev={row[2]:,.0f}")

engine.dispose()