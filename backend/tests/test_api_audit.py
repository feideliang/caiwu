"""Tests for audit log API endpoints."""
import pytest
from httpx import AsyncClient


class TestAuditAPI:
    async def test_list_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/audit/logs")
        assert resp.status_code == 403

    async def test_list_empty_admin(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/audit/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "items" in data["data"]
        assert "total" in data["data"]

    async def test_list_pagination(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/audit/logs?page=1&page_size=10")
        assert resp.status_code == 200
