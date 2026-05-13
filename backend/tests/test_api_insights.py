"""Integration tests for insights API: CRUD + status transitions."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.v3 import Insight


@pytest.mark.anyio
class TestInsightsAPI:

    async def test_list_insights_empty(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/insights?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["total"] == 0

    async def test_list_insights_with_data(self, admin_client: AsyncClient, db_session: AsyncSession):
        # Seed an insight
        insight = Insight(
            title="Revenue spike detected",
            insight_type="anomaly",
            content="Revenue increased by 30% compared to last month.",
            data_json={"__status": "unread", "metric": "revenue"},
        )
        db_session.add(insight)
        await db_session.flush()

        resp = await admin_client.get("/api/v1/insights?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] >= 1

    async def test_list_insights_type_filter(self, admin_client: AsyncClient, db_session: AsyncSession):
        insight = Insight(
            title="Trend insight",
            insight_type="trend",
            content="Growing trend detected.",
        )
        db_session.add(insight)
        await db_session.flush()

        resp = await admin_client.get("/api/v1/insights?page=1&page_size=10&insight_type=trend")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] >= 1

    async def test_get_insight_by_id(self, admin_client: AsyncClient, db_session: AsyncSession):
        insight = Insight(
            title="Test insight",
            insight_type="summary",
            content="Summary content.",
        )
        db_session.add(insight)
        await db_session.flush()
        await db_session.refresh(insight)

        resp = await admin_client.get(f"/api/v1/insights/{insight.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["title"] == "Test insight"

    async def test_get_insight_not_found(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/insights/999999")
        assert resp.status_code == 404

    async def test_update_insight_status(self, admin_client: AsyncClient, db_session: AsyncSession):
        insight = Insight(
            title="Status test",
            insight_type="anomaly",
            content="Content.",
            data_json={"__status": "unread"},
        )
        db_session.add(insight)
        await db_session.flush()
        await db_session.refresh(insight)

        resp = await admin_client.post(
            f"/api/v1/insights/{insight.id}/status",
            json={"status": "read"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "read"

    async def test_update_insight_status_not_found(self, admin_client: AsyncClient):
        resp = await admin_client.post(
            "/api/v1/insights/999999/status",
            json={"status": "read"},
        )
        assert resp.status_code == 404

    async def test_status_transitions(self, admin_client: AsyncClient, db_session: AsyncSession):
        """Test various status transitions: unread -> read -> process -> ignore."""
        insight = Insight(
            title="Transition test",
            insight_type="anomaly",
            content="Content.",
            data_json={"__status": "unread"},
        )
        db_session.add(insight)
        await db_session.flush()
        await db_session.refresh(insight)

        # unread -> read
        resp = await admin_client.post(
            f"/api/v1/insights/{insight.id}/status",
            json={"status": "read"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "read"

        # read -> process
        resp = await admin_client.post(
            f"/api/v1/insights/{insight.id}/status",
            json={"status": "process"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "process"

        # process -> ignore
        resp = await admin_client.post(
            f"/api/v1/insights/{insight.id}/status",
            json={"status": "ignore"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "ignore"

    async def test_insights_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/insights?page=1&page_size=10")
        assert resp.status_code in (401, 403)
