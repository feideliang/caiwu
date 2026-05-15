"""Verify database state after cleanup."""
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
    # Total rows by metric_name
    r = conn.execute(text("""
        SELECT metric_name, COUNT(*), SUM(metric_value)
        FROM financial_data
        GROUP BY metric_name
        ORDER BY metric_name
    """))
    print("=== Rows by metric_name ===")
    for row in r:
        print(f"  {row[0]} | count={row[1]} | sum={row[2]:,.2f}")

    # Revenue by period (2026)
    r2 = conn.execute(text("""
        SELECT period, COUNT(*), SUM(metric_value)
        FROM financial_data
        WHERE metric_name = 'revenue' AND period LIKE '2026-%'
        GROUP BY period ORDER BY period
    """))
    print("\n=== Revenue by period (2026) ===")
    for row in r2:
        print(f"  {row[0]} | count={row[1]} | sum={row[2]:,.2f}")

    # Revenue by period (2025)
    r3 = conn.execute(text("""
        SELECT period, COUNT(*), SUM(metric_value)
        FROM financial_data
        WHERE metric_name = 'revenue' AND period LIKE '2025-%'
        GROUP BY period ORDER BY period
    """))
    print("\n=== Revenue by period (2025) ===")
    for row in r3:
        print(f"  {row[0]} | count={row[1]} | sum={row[2]:,.2f}")

engine.dispose()