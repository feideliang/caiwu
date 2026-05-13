"""Integration tests for drill-down API: RESTful hierarchical paths."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import FinancialData


@pytest.mark.anyio
class TestDrilldownsAPI:

    async def test_drilldown_summary(self, admin_client: AsyncClient, db_session: AsyncSession):
        """GET /drilldowns/{report_id}/summary"""
        # Seed data for period 2024
        data_rows = [
            FinancialData(metric_name="revenue", metric_value=1000 + i, period=f"2024-{m:02d}", entity=f"Dept{i % 3}")
            for i, m in enumerate(range(1, 13))
        ]
        db_session.add_all(data_rows)
        await db_session.flush()

        resp = await admin_client.get("/api/v1/drilldowns/2024/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "total_revenue" in data["data"]

    async def test_drilldown_departments(self, admin_client: AsyncClient, db_session: AsyncSession):
        """GET /drilldowns/{report_id}/departments"""
        data_rows = [
            FinancialData(metric_name="revenue", metric_value=100, period="2024-01", entity="Sales"),
            FinancialData(metric_name="revenue", metric_value=200, period="2024-01", entity="Engineering"),
        ]
        db_session.add_all(data_rows)
        await db_session.flush()

        resp = await admin_client.get("/api/v1/drilldowns/2024/departments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    async def test_drilldown_empty_period(self, admin_client: AsyncClient):
        """Summary for period with no data."""
        resp = await admin_client.get("/api/v1/drilldowns/2099/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["total_revenue"] == 0.0

    async def test_drilldown_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/drilldowns/2024/summary")
        assert resp.status_code in (401, 403)
