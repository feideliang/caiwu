"""Tests for AI recommendation API endpoints."""
import pytest
from httpx import AsyncClient


class TestAIAPI:
    async def test_recommend_chart_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/ai/recommend/chart", json={})
        assert resp.status_code == 403

    async def test_recommend_chart(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/v1/ai/recommend/chart", json={
            "data_description": {
                "columns": ["period", "revenue"],
                "row_count": 12,
                "time_series": True,
            },
            "analysis_goal": "trend",
        })
        assert resp.status_code == 200

    async def test_recommend_layout_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/ai/recommend/layout", json={})
        assert resp.status_code == 403

    async def test_recommend_layout(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/v1/ai/recommend/layout", json={
            "chart_ids": [1, 2, 3],
            "device_type": "web",
        })
        assert resp.status_code == 200
