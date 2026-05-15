"""Add mock 直签 (direct-sign) contract_type data to financial_data."""
import asyncio
import json

from app.db.session import async_session_factory
from app.models.core import FinancialData

# Pick existing rows that don't have contract_type and add mock 直签 tags
# Strategy: find revenue rows with customer tags, mark ~30% as 直签

async def main():
    async with async_session_factory() as db:
        from sqlalchemy import select, text

        # Find all rows with customer tags but no contract_type
        stmt = text("""
            SELECT id, tags, period, metric_name
            FROM financial_data
            WHERE tags IS NOT NULL
              AND tags->>'customer' IS NOT NULL
              AND tags->>'contract_type' IS NULL
              AND metric_name IN ('revenue', '营业收入', 'sales', 'cost', 'gross_profit', '毛利润')
            ORDER BY period, id
            LIMIT 200
        """)
        rows = (await db.execute(stmt)).all()
        print(f"Found {len(rows)} rows without contract_type")

        import random
        random.seed(42)

        updated = 0
        for row in rows:
            if random.random() < 0.35:  # ~35% become 直签
                new_tags = json.loads(row[1]) if isinstance(row[1], str) else row[1].copy()
                new_tags['contract_type'] = '直签'
                await db.execute(
                    text("UPDATE financial_data SET tags = :tags WHERE id = :id"),
                    {"tags": json.dumps(new_tags, ensure_ascii=False), "id": row[0]}
                )
                updated += 1

        await db.commit()
        print(f"Updated {updated} rows with contract_type='直签'")

        # Verify
        verify = text("SELECT COUNT(*) FROM financial_data WHERE tags->>'contract_type' = '直签'")
        count = (await db.execute(verify)).scalar()
        print(f"Total 直签 rows now: {count}")

asyncio.run(main())
