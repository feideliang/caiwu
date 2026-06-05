"""Check distinct product_line values in financial_data."""
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
    r = conn.execute(text("""
        SELECT DISTINCT tags->>'product_bgbu'
        FROM financial_data
        WHERE metric_name = 'revenue' AND period LIKE '2026-%'
        ORDER BY 1
    """))
    print("=== Distinct product_line values (2026) ===")
    for row in r:
        print(f"  {row[0]}")

    r2 = conn.execute(text("""
        SELECT tags->>'product_bgbu', COUNT(*), SUM(metric_value)
        FROM financial_data
        WHERE metric_name = 'revenue' AND period LIKE '2026-%'
        GROUP BY tags->>'product_bgbu'
        ORDER BY 3 DESC
    """))
    print("\n=== Revenue by product_line (2026) ===")
    for row in r2:
        print(f"  {row[0]}: count={row[1]}, sum={row[2]:,.0f}")

engine.dispose()