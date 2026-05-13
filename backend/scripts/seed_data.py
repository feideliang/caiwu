"""Seed initial data: roles and admin user."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from app.db.session import engine
from app.core.security import hash_password


async def seed():
    async with engine.connect() as conn:
        # Check if roles already exist
        result = await conn.execute(text("SELECT count(*) FROM roles"))
        role_count = result.scalar()
        if role_count > 0:
            print(f"Roles already exist ({role_count} roles), skipping role seed.")
        else:
            await conn.execute(text("""
                INSERT INTO roles (name, permissions, display_name, description) VALUES
                ('admin', '["*"]', 'Administrator', 'System administrator - full access'),
                ('analyst', '["dashboard:*", "report:*", "data:*", "analysis:*"]', 'Analyst', 'Data analyst - read + analysis'),
                ('viewer', '["dashboard:*"]', 'Viewer', 'Read-only viewer')
            """))
            print("Created 3 roles: admin, analyst, viewer")

        # Check if admin user already exists
        result = await conn.execute(text("SELECT count(*) FROM users WHERE username = 'admin'"))
        user_count = result.scalar()
        if user_count > 0:
            print("Admin user already exists, skipping.")
        else:
            # Get admin role_id
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'admin' LIMIT 1"))
            admin_role_id = result.scalar()

            hashed = hash_password("admin123")
            await conn.execute(text("""
                INSERT INTO users (username, password_hash, email, role_id, is_active)
                VALUES ('admin', :pwd, 'admin@caiwu.local', :role_id, true)
            """), {"pwd": hashed, "role_id": admin_role_id})
            print("Created admin user (password: admin123)")

        await conn.commit()
        print("Seed complete.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
