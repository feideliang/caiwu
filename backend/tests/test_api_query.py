"""Tests for query API endpoints."""
import pytest
from httpx import AsyncClient


class TestQueryAPI:
    async def test_query_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/query", json={})
        assert resp.status_code == 403

    async def test_query_unknown_table(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/v1/query", json={"table": "nonexistent"})
        assert resp.status_code in (200, 404)

    async def test_query_with_filters(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/v1/query", json={
            "table": "financial_data",
            "page": 1,
            "page_size": 10,
        })
        assert resp.status_code == 200
