"""Integration tests for dashboard BFF API with cache."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.anyio
class TestDashboardAPI:

    async def test_dashboard_bff_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/dashboard/bff",
            json={"device_type": "web"},
        )
        assert resp.status_code in (401, 403)

    async def test_dashboard_bff_with_layout(self, admin_client: AsyncClient, db_session: AsyncSession):
        # Create a layout first
        from app.models.core import DashboardLayout, ChartConfig

        chart = ChartConfig(name="Test Chart", chart_type="line")
        db_session.add(chart)
        await db_session.flush()

        layout = DashboardLayout(
            name="Test Dashboard",
            device_type="web",
            chart_ids=[chart.id],
            layout_config={"type": "grid"},
        )
        db_session.add(layout)
        await db_session.flush()

        resp = await admin_client.post(
            "/api/v1/dashboard/bff",
            json={"device_type": "web", "bypass_cache": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "dashboard_id" in data["data"]

    async def test_dashboard_bff_no_layout_fallback(self, admin_client: AsyncClient):
        # Without any layout, should return 404
        resp = await admin_client.post(
            "/api/v1/dashboard/bff",
            json={"device_type": "nonexistent_device"},
        )
        assert resp.status_code == 404

    async def test_list_insights_empty(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/dashboard/insights?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["total"] == 0

    async def test_list_insights_with_type_filter(self, admin_client: AsyncClient):
        resp = await admin_client.get(
            "/api/v1/dashboard/insights?page=1&page_size=10&insight_type=anomaly"
        )
        assert resp.status_code == 200
