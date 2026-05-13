"""Shared test fixtures for the entire test suite."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db.session import get_db
from app.main import create_app
from app.models.core import Base
import app.models.v3  # noqa: F401
import app.models.v4  # noqa: F401
from app.models.v4 import Role, User

TEST_DB_URL = "postgresql+asyncpg://learnhouse:learnhouse@localhost:5432/caiwu_test"


async def _reset_schema(conn):
    """Drop and recreate the public schema — clears tables AND enum types."""
    from sqlalchemy import text
    await conn.execute(text("SET LOCAL lock_timeout = '30s'"))
    await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))
    await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))


async def _reset_with_retry(eng, attempts: int = 3):
    """Reset schema, retrying on transient lock contention."""
    from sqlalchemy.exc import OperationalError, DBAPIError
    last_err = None
    for i in range(attempts):
        try:
            async with eng.begin() as conn:
                await _reset_schema(conn)
                await conn.run_sync(Base.metadata.create_all)
            return
        except (OperationalError, DBAPIError) as e:
            last_err = e
            await asyncio.sleep(0.2 * (i + 1))
    raise last_err


# Per-test engine with NullPool — each test gets a fresh engine that is
# disposed at teardown so schema-reset never races against stale connections.

@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a fresh engine per test, reset schema, dispose on teardown."""
    from sqlalchemy.pool import NullPool
    eng = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
    await _reset_with_retry(eng)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Per-test async session that rolls back and closes at teardown.

    Explicitly closes the session (and its underlying connection) before the
    fixture returns, so the next test's schema reset does not race against a
    connection that is still being returned to the pool.
    """
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        try:
            await session.rollback()
        except Exception:
            pass
        await session.close()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Test HTTP client with DB override."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def seeded_db(db_session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """DB with all 3 roles and a default admin user pre-created."""
    for name, display_name, perms in [
        ("admin", "Admin", ["*"]),
        ("analyst", "Analyst", ["dashboard:*", "report:*", "data:*", "analysis:*"]),
        ("viewer", "Viewer", ["dashboard:*"]),
    ]:
        result = await db_session.execute(select(Role).where(Role.name == name))
        if result.scalar_one_or_none() is None:
            db_session.add(Role(name=name, display_name=display_name, permissions=perms))
    await db_session.flush()

    user = User(
        username="test_admin",
        email="admin@test.com",
        password_hash=hash_password("testpass123"),
        role_id=1,
    )
    db_session.add(user)
    await db_session.flush()
    yield db_session


@pytest_asyncio.fixture(scope="function")
async def admin_client(seeded_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with an admin JWT already loaded."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: seeded_db

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"username": "test_admin", "password": "testpass123"},
            )
            token = resp.json()["data"]["access_token"]
            ac.headers["Authorization"] = f"Bearer {token}"
            yield ac
    finally:
        app.dependency_overrides.clear()


# ── Sample data fixtures ────────────────────────────────────


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create a sample DataFrame with 1000 rows of financial data."""
    import random

    metrics = [
        "revenue", "cost", "gross_profit_rate", "net_profit_rate",
        "dso", "ito", "dpo", "cash_conversion_cycle",
        "ar_amount", "ap_amount", "inventory",
    ]
    periods = [f"2024-{m:02d}" for m in range(1, 13)]
    entities = ["CompanyA", "CompanyB", "CompanyC", None, ""]

    rows = []
    for i in range(1000):
        metric = random.choice(metrics)
        period = random.choice(periods)
        entity = random.choice(entities)
        if entity == "":
            entity = None

        value_map = {
            "revenue": random.uniform(100000, 10000000),
            "cost": random.uniform(50000, 8000000),
            "gross_profit_rate": random.uniform(-0.2, 0.8),
            "net_profit_rate": random.uniform(-0.1, 0.5),
            "dso": random.uniform(10, 120),
            "ito": random.uniform(5, 90),
            "dpo": random.uniform(10, 100),
            "cash_conversion_cycle": random.uniform(-30, 150),
            "ar_amount": random.uniform(10000, 5000000),
            "ap_amount": random.uniform(10000, 5000000),
            "inventory": random.uniform(5000, 3000000),
        }

        rows.append({
            "metric_name": metric,
            "metric_value": value_map.get(metric, random.uniform(0, 1000000)),
            "metric_unit": "CNY" if metric in ("revenue", "cost") else "",
            "period": period,
            "entity": entity,
        })

    return pd.DataFrame(rows)


@pytest.fixture
def sample_excel_path(sample_dataframe: pd.DataFrame) -> str:
    """Create a temp Excel file with sample data. Returns path."""
    fd, path = tempfile.mkstemp(suffix=".xlsx", prefix="test_sample_")
    os.close(fd)
    sample_dataframe.to_excel(path, index=False, engine="openpyxl")
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_xls_path(sample_dataframe: pd.DataFrame) -> str:
    """Create a temp .xls file with sample data."""
    fd, path = tempfile.mkstemp(suffix=".xls", prefix="test_sample_")
    os.close(fd)
    sample_dataframe.to_excel(path, index=False, engine="openpyxl")
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_excel_with_bad_columns() -> str:
    """Excel file with non-standard column names requiring fuzzy matching."""
    df = pd.DataFrame({
        "指标名称": ["revenue", "cost", "DSO"],
        "指标值": [1000000, 500000, 45.0],
        "期间": ["2024-01", "2024-01", "2024-01"],
        "公司": ["CompanyA", "CompanyA", "CompanyA"],
    })
    fd, path = tempfile.mkstemp(suffix=".xlsx", prefix="test_chinese_")
    os.close(fd)
    df.to_excel(path, index=False, engine="openpyxl")
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_excel_with_invalid_data() -> str:
    """Excel file with some invalid rows (out of range, missing fields)."""
    df = pd.DataFrame({
        "metric_name": ["revenue", "gross_profit_rate", "cost", "revenue", ""],
        "metric_value": [1000000, 1.5, 500000, -500, 100],  # 1.5>1, -500<0, empty name
        "period": ["2024-01", "2024-01", "2024-01", "2024-02", "2024-01"],
        "entity": ["A", "A", "A", "A", "A"],
    })
    fd, path = tempfile.mkstemp(suffix=".xlsx", prefix="test_invalid_")
    os.close(fd)
    df.to_excel(path, index=False, engine="openpyxl")
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_excel_with_duplicates() -> str:
    """Excel file with duplicate rows."""
    df = pd.DataFrame({
        "metric_name": ["revenue", "revenue", "cost", "cost", "dso"],
        "metric_value": [1000000, 1200000, 500000, 600000, 45],
        "period": ["2024-01", "2024-01", "2024-01", "2024-01", "2024-01"],
        "entity": ["A", "A", "A", "A", "A"],
    })
    fd, path = tempfile.mkstemp(suffix=".xlsx", prefix="test_dupes_")
    os.close(fd)
    df.to_excel(path, index=False, engine="openpyxl")
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_excel_with_date_variations() -> str:
    """Excel file with various date formats."""
    df = pd.DataFrame({
        "metric_name": ["revenue"] * 5,
        "metric_value": [100, 200, 300, 400, 500],
        "period": ["2024-01", "2024/01/15", "2024Q1", "2024年1月", "202401"],
        "entity": ["A"] * 5,
    })
    fd, path = tempfile.mkstemp(suffix=".xlsx", prefix="test_dates_")
    os.close(fd)
    df.to_excel(path, index=False, engine="openpyxl")
    yield path
    if os.path.exists(path):
        os.unlink(path)


# ── IMAP mock fixtures ──────────────────────────────────────


@pytest.fixture
def mock_imap_connection():
    """Mock IMAP connection object."""
    conn = MagicMock()
    conn.select.return_value = ("OK", [b"0"])
    conn.uid.return_value = ("OK", [b"1 2 3"])
    conn.login.return_value = ("OK", [b""])
    conn.noop.return_value = ("OK", [b""])
    conn.logout.return_value = ("BYE", [b""])
    return conn


@pytest.fixture
def mock_email_message():
    """Mock email.message.Message with attachment."""
    import email
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders
    import io

    msg = MIMEMultipart()
    msg["Subject"] = "Financial Report - January 2024"
    msg["From"] = "finance@example.com"
    msg["Date"] = "Mon, 1 Jan 2024 00:00:00 +0000"

    # Create a fake Excel attachment
    excel_content = b"fake_excel_content"
    part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    part.set_payload(excel_content)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename="report.xlsx")
    msg.attach(part)

    return msg


@pytest.fixture
def mock_email_without_attachment():
    """Mock email.message.Message without attachments."""
    import email
    from email.mime.text import MIMEText

    msg = MIMEText("This is just text, no attachments.")
    msg["Subject"] = "Meeting notes"
    msg["From"] = "colleague@example.com"
    msg["Date"] = "Mon, 1 Jan 2024 00:00:00 +0000"
    return msg


@pytest.fixture
def uid_tracker(tmp_path):
    """Create a ProcessedUIDTracker with a temp file."""
    from app.services.email_reader import ProcessedUIDTracker
    filepath = str(tmp_path / "processed_uids.json")
    return ProcessedUIDTracker(filepath=filepath)


# ── Redis mock fixtures ─────────────────────────────────────


@pytest.fixture
def mock_redis():
    """Mock Redis client for locking."""
    redis_mock = MagicMock()
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    return redis_mock


@pytest.fixture
def mock_redis_locked():
    """Mock Redis client that returns lock already held."""
    redis_mock = MagicMock()
    redis_mock.set.return_value = False
    return redis_mock


# ── Cache mock ──────────────────────────────────────────────


@pytest.fixture
def mock_cache():
    """Mock cache functions to avoid Redis dependency in tests."""
    with patch("app.core.cache.cache_get", return_value=None), \
         patch("app.core.cache.cache_set", return_value=None), \
         patch("app.core.cache.cache_delete_pattern", return_value=None), \
         patch("app.core.cache.get_redis", return_value=MagicMock()):
        yield
