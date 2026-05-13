"""Tests for notification API endpoints."""
import pytest
from httpx import AsyncClient


class TestNotificationsAPI:
    async def test_list_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/notifications")
        assert resp.status_code == 403

    async def test_list_empty(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "items" in data["data"]
        assert "total" in data["data"]

    async def test_mark_read_no_notification(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/v1/notifications/999/read")
        assert resp.status_code == 404

    async def test_read_all(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/v1/notifications/read-all")
        assert resp.status_code == 200
