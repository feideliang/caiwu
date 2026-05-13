"""Integration tests for filter options and filter-views CRUD."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import FinancialData
from app.models.v3 import FilterView


@pytest.mark.anyio
class TestFilterOptionsAPI:

    async def test_get_filter_options_period(self, admin_client: AsyncClient, db_session: AsyncSession):
        # Seed some data
        fd = FinancialData(metric_name="revenue", metric_value=100, period="2024-01", entity="A")
        db_session.add(fd)
        await db_session.flush()

        resp = await admin_client.get("/api/v1/filter-options?dimension=period")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "2024-01" in data["data"]["options"]

    async def test_get_filter_options_entity(self, admin_client: AsyncClient, db_session: AsyncSession):
        fd = FinancialData(metric_name="revenue", metric_value=100, period="2024-01", entity="CompanyX")
        db_session.add(fd)
        await db_session.flush()

        resp = await admin_client.get("/api/v1/filter-options?dimension=entity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["dimension"] == "entity"

    async def test_get_filter_options_metric_name(self, admin_client: AsyncClient, db_session: AsyncSession):
        fd = FinancialData(metric_name="dso", metric_value=45, period="2024-01")
        db_session.add(fd)
        await db_session.flush()

        resp = await admin_client.get("/api/v1/filter-options?dimension=metric_name")
        assert resp.status_code == 200
        data = resp.json()
        assert "dso" in data["data"]["options"]

    async def test_get_filter_options_with_prefix(self, admin_client: AsyncClient, db_session: AsyncSession):
        fds = [
            FinancialData(metric_name="revenue", metric_value=100, period="2024-01"),
            FinancialData(metric_name="revenue_q1", metric_value=200, period="2024-01"),
            FinancialData(metric_name="cost", metric_value=50, period="2024-01"),
        ]
        db_session.add_all(fds)
        await db_session.flush()

        resp = await admin_client.get("/api/v1/filter-options?dimension=metric_name&prefix=rev")
        assert resp.status_code == 200
        data = resp.json()
        options = data["data"]["options"]
        assert all("rev" in o for o in options)

    async def test_get_filter_options_invalid_dimension(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/filter-options?dimension=invalid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["options"] == []

    async def test_filter_options_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/filter-options?dimension=period")
        assert resp.status_code in (401, 403)


@pytest.mark.anyio
class TestFilterViewsAPI:

    async def test_list_filter_views_empty(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/filter-views?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["total"] == 0

    async def test_create_filter_view(self, admin_client: AsyncClient):
        resp = await admin_client.post(
            "/api/v1/filter-views",
            json={
                "name": "Q1 2024 View",
                "filters": {"period": "2024-Q1", "entity": "CompanyA"},
                "is_public": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "Q1 2024 View"
        assert "id" in data["data"]

    async def test_create_public_filter_view(self, admin_client: AsyncClient):
        resp = await admin_client.post(
            "/api/v1/filter-views",
            json={
                "name": "Public View",
                "filters": {"period": "2024-Q1"},
                "is_public": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["is_public"] is True

    async def test_list_filter_views_after_create(self, admin_client: AsyncClient):
        # Create first
        await admin_client.post(
            "/api/v1/filter-views",
            json={"name": "View A", "filters": {"period": "2024-Q1"}, "is_public": False},
        )

        # Then list
        resp = await admin_client.get("/api/v1/filter-views?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] >= 1

    async def test_delete_filter_view(self, admin_client: AsyncClient):
        # Create
        resp = await admin_client.post(
            "/api/v1/filter-views",
            json={"name": "To Delete", "filters": {}, "is_public": False},
        )
        view_id = resp.json()["data"]["id"]

        # Delete
        resp = await admin_client.delete(f"/api/v1/filter-views/{view_id}")
        assert resp.status_code == 200

        # Verify gone
        resp = await admin_client.get("/api/v1/filter-views?page=1&page_size=10")
        data = resp.json()
        ids = [v["id"] for v in data["data"]["items"]]
        assert view_id not in ids

    async def test_delete_nonexistent_filter_view(self, admin_client: AsyncClient):
        resp = await admin_client.delete("/api/v1/filter-views/999999")
        assert resp.status_code == 404

    async def test_filter_views_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/filter-views?page=1&page_size=10")
        assert resp.status_code in (401, 403)
