"""Add missing roles (analyst, viewer) to the database."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from app.db.session import engine


async def add_roles():
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT name, id FROM roles'))
        rows = result.all()
        print('Existing roles:', [(r[0], r[1]) for r in rows])

        existing_names = [r[0] for r in rows]
        if 'analyst' not in existing_names:
            await conn.execute(text("""
                INSERT INTO roles (name, permissions, display_name, description) VALUES
                ('analyst', '["dashboard:*","report:*","data:*","analysis:*"]', 'Analyst', 'Data analyst')
            """))
            print('Created analyst role')

        if 'viewer' not in existing_names:
            await conn.execute(text("""
                INSERT INTO roles (name, permissions, display_name, description) VALUES
                ('viewer', '["dashboard:*"]', 'Viewer', 'Read-only viewer')
            """))
            print('Created viewer role')

        await conn.commit()

        result2 = await conn.execute(text('SELECT name, id FROM roles'))
        rows2 = result2.all()
        print('All roles:', [(r[0], r[1]) for r in rows2])

    await engine.dispose()

asyncio.run(add_roles())