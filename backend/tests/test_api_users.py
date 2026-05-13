"""Tests for user CRUD API endpoints."""
import pytest
from httpx import AsyncClient


class TestUsersAPI:
    async def test_create_requires_admin(self, client: AsyncClient):
        resp = await client.post("/api/v1/users", json={"username": "test", "password": "test123", "role_id": 2})
        assert resp.status_code == 403

    async def test_create_user(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/v1/users", json={
            "username": "newuser",
            "password": "test123",
            "email": "new@test.com",
            "role_id": 2,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "id" in data["data"]

    async def test_create_duplicate_username(self, admin_client: AsyncClient):
        first = await admin_client.post("/api/v1/users", json={
            "username": "dupuser",
            "password": "test123",
            "email": "dup@test.com",
            "role_id": 2,
        })
        assert first.status_code == 200
        assert first.json()["code"] == 0

        resp = await admin_client.post("/api/v1/users", json={
            "username": "dupuser",
            "password": "test123",
            "role_id": 2,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] != 0  # should be error

    async def test_list_users_admin(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/users")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "items" in data["data"]
        assert "total" in data["data"]

    async def test_delete_user(self, admin_client: AsyncClient):
        resp = await admin_client.delete("/api/v1/users/999")
        assert resp.status_code == 404

    async def test_non_admin_cannot_list(self, client: AsyncClient):
        """No auth token → 403/401"""
        resp = await client.get("/api/v1/users")
        assert resp.status_code in (401, 403)
