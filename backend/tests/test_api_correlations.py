"""Integration tests for correlations API: analyze + calibrate."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import FinancialData
from app.models.v3 import CorrelationResult


@pytest.mark.anyio
class TestCorrelationsAPI:

    async def test_analyze_correlation_requires_data(self, admin_client: AsyncClient, db_session: AsyncSession):
        """Correlation analysis needs overlapping data."""
        # Seed overlapping data for two metrics
        data_rows = [
            FinancialData(metric_name="revenue", metric_value=100 + i * 10, period=f"2024-{i+1:02d}")
            for i in range(12)
        ] + [
            FinancialData(metric_name="cost", metric_value=50 + i * 5, period=f"2024-{i+1:02d}")
            for i in range(12)
        ]
        db_session.add_all(data_rows)
        await db_session.flush()

        resp = await admin_client.post(
            "/api/v1/correlations/analyze",
            json={
                "metric_a": "revenue",
                "metric_b": "cost",
                "method": "pearson",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "coefficient" in data["data"]

    async def test_analyze_correlation_insufficient_data(self, admin_client: AsyncClient, db_session: AsyncSession):
        """Need at least 3 overlapping periods."""
        data_rows = [
            FinancialData(metric_name="revenue", metric_value=100, period="2024-01"),
            FinancialData(metric_name="cost", metric_value=50, period="2024-01"),
        ]
        db_session.add_all(data_rows)
        await db_session.flush()

        resp = await admin_client.post(
            "/api/v1/correlations/analyze",
            json={
                "metric_a": "revenue",
                "metric_b": "cost",
                "method": "pearson",
            },
        )
        assert resp.status_code == 400  # Business error

    async def test_analyze_spearman(self, admin_client: AsyncClient, db_session: AsyncSession):
        data_rows = [
            FinancialData(metric_name="revenue", metric_value=100 + i * 10, period=f"2024-{i+1:02d}")
            for i in range(6)
        ] + [
            FinancialData(metric_name="cost", metric_value=50 + i * 5, period=f"2024-{i+1:02d}")
            for i in range(6)
        ]
        db_session.add_all(data_rows)
        await db_session.flush()

        resp = await admin_client.post(
            "/api/v1/correlations/analyze",
            json={
                "metric_a": "revenue",
                "metric_b": "cost",
                "method": "spearman",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "coefficient" in data["data"]

    async def test_list_correlations(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/correlations?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "items" in data["data"]

    async def test_calibrate_correlation(self, admin_client: AsyncClient, db_session: AsyncSession):
        # Create a correlation result first
        corr = CorrelationResult(
            metric_a="revenue",
            metric_b="cost",
            coefficient=0.85,
            p_value=0.001,
            sample_size=12,
            period_start="2024-01",
            period_end="2024-12",
        )
        db_session.add(corr)
        await db_session.flush()
        await db_session.refresh(corr)

        resp = await admin_client.post(
            f"/api/v1/correlations/{corr.id}/calibrate",
            json={
                "action": "confirm",
                "calibrated_coefficient": 0.85,
                "notes": "Looks correct",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["correlation_id"] == corr.id

    async def test_calibrate_nonexistent_correlation(self, admin_client: AsyncClient):
        resp = await admin_client.post(
            "/api/v1/correlations/999999/calibrate",
            json={"action": "confirm"},
        )
        assert resp.status_code == 404

    async def test_correlations_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/correlations?page=1&page_size=10")
        assert resp.status_code in (401, 403)
