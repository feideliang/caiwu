"""Tests for system API endpoints."""
import pytest
from httpx import AsyncClient


class TestSystemAPI:
    async def test_data_freshness_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/system/data-freshness")
        assert resp.status_code == 403

    async def test_data_freshness_shape(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/system/data-freshness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        fields = ["last_sync_time", "data_range", "status", "next_sync_at"]
        for f in fields:
            assert f in data["data"]
