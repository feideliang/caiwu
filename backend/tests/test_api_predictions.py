"""Integration tests for predictions API: create + result."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import FinancialData
from app.models.v3 import PredictionResult


@pytest.mark.anyio
class TestPredictionsAPI:

    async def test_create_prediction(self, admin_client: AsyncClient, db_session: AsyncSession):
        """Create a prediction task. Requires 12 months of history."""
        # Seed 12+ months of data
        data_rows = [
            FinancialData(metric_name="revenue", metric_value=1000 + i * 50, period=f"2023-{m:02d}")
            for i, m in enumerate(range(1, 13))
        ]
        db_session.add_all(data_rows)
        await db_session.flush()

        resp = await admin_client.post(
            "/api/v1/predictions",
            json={
                "metric_name": "revenue",
                "prediction_type": "forecast",
                "horizon": 3,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "processing"

    async def test_create_prediction_insufficient_history(self, admin_client: AsyncClient):
        """Less than 12 months of data should fail."""
        resp = await admin_client.post(
            "/api/v1/predictions",
            json={
                "metric_name": "revenue",
                "prediction_type": "forecast",
                "horizon": 3,
            },
        )
        assert resp.status_code == 400  # Business error

    async def test_create_prediction_anomaly_detection(self, admin_client: AsyncClient, db_session: AsyncSession):
        """Create anomaly detection prediction."""
        data_rows = [
            FinancialData(metric_name="cost", metric_value=500 + i * 10, period=f"2023-{m:02d}")
            for i, m in enumerate(range(1, 13))
        ]
        db_session.add_all(data_rows)
        await db_session.flush()

        resp = await admin_client.post(
            "/api/v1/predictions",
            json={
                "metric_name": "cost",
                "prediction_type": "anomaly_detection",
                "horizon": 1,
            },
        )
        assert resp.status_code == 201

    async def test_get_prediction(self, admin_client: AsyncClient, db_session: AsyncSession):
        """Get a prediction result by ID."""
        pred = PredictionResult(
            metric_name="revenue",
            prediction_type="forecast",
            horizon=3,
            predicted_values={"2024-01": 1500, "2024-02": 1600, "2024-03": 1700},
            confidence_interval={"2024-01": [1400, 1600]},
            model_name="simple_linear",
            accuracy_score=0.85,
        )
        db_session.add(pred)
        await db_session.flush()
        await db_session.refresh(pred)

        resp = await admin_client.get(f"/api/v1/predictions/{pred.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["metric_name"] == "revenue"
        assert data["data"]["horizon"] == 3

    async def test_get_prediction_not_found(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/v1/predictions/999999")
        assert resp.status_code == 404

    async def test_predictions_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/predictions",
            json={"metric_name": "revenue", "prediction_type": "forecast", "horizon": 3},
        )
        assert resp.status_code in (401, 403)
