"""Auth endpoint tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.v4 import Role, User


@pytest.mark.anyio
async def test_health_check(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.anyio
async def test_login_success(seeded_db: AsyncSession, client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "test_admin", "password": "testpass123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "access_token" in body["data"]


@pytest.mark.anyio
async def test_login_wrong_password(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "test_admin", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == 4010


@pytest.mark.anyio
async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "x"},
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_me_endpoint(admin_client: AsyncClient):
    resp = await admin_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["username"] == "test_admin"


@pytest.mark.anyio
async def test_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403  # HTTPBearer rejects without token


@pytest.mark.anyio
async def test_password_hashing():
    pw = hash_password("secret123")
    assert verify_password("secret123", pw)
    assert not verify_password("wrong", pw)


@pytest.mark.anyio
async def test_list_users_admin_only(admin_client: AsyncClient):
    resp = await admin_client.get("/api/v1/users?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
