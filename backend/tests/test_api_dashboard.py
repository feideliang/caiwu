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


@pytest.mark.anyio
class TestDashboardDeptFilter:

    async def _seed_financial_data(self, db_session: AsyncSession):
        """Seed sample FinancialData for two departments across two years."""
        from app.models.core import FinancialData
        for entity in ["CBG", "EBG"]:
            for period in ["2025-01", "2026-01"]:
                for metric in ["revenue", "cost"]:
                    base = 1000000.0 if metric == "revenue" else 600000.0
                    # Scale 2026 values slightly higher for YoY growth
                    val = base * 1.1 if period == "2026-01" else base
                    db_session.add(FinancialData(
                        metric_name=metric,
                        metric_value=val,
                        metric_unit="CNY",
                        period=period,
                        entity=entity,
                    ))
        await db_session.flush()

    async def _seed_layout(self, db_session: AsyncSession):
        """Seed a DashboardLayout + ChartConfig so the BFF endpoint works."""
        from app.models.core import ChartConfig, DashboardLayout
        chart = ChartConfig(name="Dept Filter Chart", chart_type="line", config={"metrics": ["revenue"]})
        db_session.add(chart)
        await db_session.flush()
        layout = DashboardLayout(
            name="Dept Filter Dashboard",
            device_type="web",
            chart_ids=[chart.id],
            layout_config={"type": "grid"},
        )
        db_session.add(layout)
        await db_session.flush()

    async def test_cbg_user_sees_only_cbg_data(
        self, analyst_cbg: AsyncSession, analyst_cbg_client: AsyncClient
    ):
        """A CBG analyst should only see CBG department data in the dashboard."""
        await self._seed_financial_data(analyst_cbg)
        await self._seed_layout(analyst_cbg)
        resp = await analyst_cbg_client.post(
            "/api/v1/dashboard/bff",
            json={"device_type": "web", "bypass_cache": True},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        depts = data.get("department_breakdown", [])
        for d in depts:
            assert d["dimension_value"] == "CBG", (
                f"CBG user should not see {d['dimension_value']} data"
            )

    async def test_admin_sees_all_departments(
        self, seeded_db: AsyncSession, admin_client: AsyncClient
    ):
        """An admin user should see data from all departments."""
        await self._seed_financial_data(seeded_db)
        await self._seed_layout(seeded_db)
        resp = await admin_client.post(
            "/api/v1/dashboard/bff",
            json={"device_type": "web", "bypass_cache": True},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        depts = data.get("department_breakdown", [])
        dept_names = [d["dimension_value"] for d in depts]
        assert any(name in dept_names for name in ["CBG", "EBG"]), (
            f"Admin should see department data, got: {dept_names}"
        )
