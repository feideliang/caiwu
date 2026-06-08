import asyncio
import os, sys
sys.path.insert(0, '.')
os.environ.setdefault('APP_ENV', 'development')

from sqlalchemy import create_engine, text
from app.core.config import settings

# Build a sync engine from settings
db_url = settings.SQLALCHEMY_DATABASE_URL
engine = create_engine(db_url)

with engine.connect() as conn:
    # Check distinct product_bgbu values in agg_dimension_summary
    result = conn.execute(text('''
        SELECT DISTINCT dim_value, COUNT(*) as cnt, SUM(revenue) as total_revenue
        FROM agg_dimension_summary
        WHERE dim_type = 'product_bgbu'
        GROUP BY dim_value
        ORDER BY total_revenue DESC
    '''))
    rows = result.fetchall()
    print('=== agg_dimension_summary (product_bgbu) ===')
    for r in rows:
        print(f'  dim_value="{r[0]}" count={r[1]} revenue={r[2]}')

    # Check periods for product_bgbu
    result = conn.execute(text('''
        SELECT DISTINCT period, bgbu
        FROM agg_dimension_summary
        WHERE dim_type = 'product_bgbu'
        LIMIT 20
    '''))
    rows = result.fetchall()
    print()
    print('=== agg_dimension_summary periods ===')
    for r in rows:
        print(f'  period="{r[0]}" bgbu="{r[1]}"')
