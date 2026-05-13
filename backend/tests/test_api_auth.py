"""Integration tests for auth API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.v4 import Role, User


@pytest.mark.anyio
class TestAuthAPI:

    async def test_health_check(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_root(self, client: AsyncClient):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "version" in resp.json()

    async def test_login_success(self, seeded_db: AsyncSession, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "test_admin", "password": "testpass123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "access_token" in body["data"]

    async def test_login_wrong_password(self, seeded_db: AsyncSession, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "test_admin", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == 4010

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "x"},
        )
        assert resp.status_code == 401

    async def test_me_endpoint(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["username"] == "test_admin"

    async def test_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 403

    async def test_list_users_admin_only(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/users?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    async def test_token_validation(self, seeded_db: AsyncSession, client: AsyncClient):
        # Login to get token
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "test_admin", "password": "testpass123"},
        )
        token = resp.json()["data"]["access_token"]

        # Use token
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert resp.status_code == 401

    async def test_empty_authorization(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 403
