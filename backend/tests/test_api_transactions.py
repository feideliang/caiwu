"""Tests for transaction analysis API endpoints."""
import pytest
from httpx import AsyncClient


class TestContractsAPI:
    async def test_contracts_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/transactions/contracts")
        assert resp.status_code == 403

    async def test_contracts_empty(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/transactions/contracts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0


class TestOrdersAPI:
    async def test_orders_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/transactions/orders")
        assert resp.status_code == 403

    async def test_orders_empty(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/transactions/orders")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0


class TestProjectsAPI:
    async def test_projects_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/transactions/projects")
        assert resp.status_code == 403

    async def test_projects_empty(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/transactions/projects")
        assert resp.status_code == 200


class TestAnomaliesAPI:
    async def test_anomalies_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/transactions/anomalies")
        assert resp.status_code == 403

    async def test_anomalies_empty(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/transactions/anomalies")
        assert resp.status_code == 200


class TestLargeAmountsAPI:
    async def test_large_amounts_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/transactions/large-amounts")
        assert resp.status_code == 403

    async def test_large_amounts_empty(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/transactions/large-amounts?threshold=999999999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["items"] == []
