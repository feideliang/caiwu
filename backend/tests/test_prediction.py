"""Tests for the prediction service and Celery task."""

from __future__ import annotations

import pytest

from app.services.prediction_service import PredictionService
from app.tasks.prediction import _compute_mape, _quality_gate, _next_periods


class TestQualityGate:
    """Test MAPE quality gate logic."""

    def test_qualified(self):
        accepted, reason = _quality_gate(10.0)
        assert accepted is True
        assert reason is None

    def test_warning_range(self):
        accepted, reason = _quality_gate(20.0)
        assert accepted is True
        assert "warning" in reason.lower()

    def test_rejected(self):
        accepted, reason = _quality_gate(30.0)
        assert accepted is False
        assert "rejected" in reason.lower()

    def test_exact_threshold_qualified(self):
        accepted, reason = _quality_gate(14.9)
        assert accepted is True
        assert reason is None


class TestNextPeriods:
    """Test period label generation."""

    def test_monthly_periods(self):
        periods = _next_periods("2024-11", 3)
        assert periods == ["2024-12", "2025-01", "2025-02"]

    def test_year_rollover(self):
        periods = _next_periods("2024-12", 2)
        assert periods == ["2025-01", "2025-02"]

    def test_quarterly_periods(self):
        periods = _next_periods("2024-Q3", 3)
        assert periods == ["2024-Q4", "2025-Q1", "2025-Q2"]

    def test_quarter_year_rollover(self):
        periods = _next_periods("2024-Q4", 2)
        assert periods == ["2025-Q1", "2025-Q2"]

    def test_fallback_format(self):
        periods = _next_periods("unknown", 2)
        assert periods == ["unknown_+1", "unknown_+2"]


class TestPredictionServiceValidation:
    """Test PredictionService input validation."""

    def test_invalid_prediction_type(self):
        with pytest.raises(Exception):  # BusinessError
            import asyncio
            async def _test():
                from unittest.mock import AsyncMock
                mock_db = AsyncMock()
                await PredictionService.create_prediction(
                    db=mock_db,
                    user_id=1,
                    metric_name="revenue",
                    prediction_type="invalid_type",
                )
            asyncio.run(_test())

    def test_horizon_too_large(self):
        with pytest.raises(Exception):
            import asyncio
            async def _test():
                from unittest.mock import AsyncMock
                mock_db = AsyncMock()
                await PredictionService.create_prediction(
                    db=mock_db,
                    user_id=1,
                    metric_name="revenue",
                    prediction_type="forecast",
                    horizon=13,
                )
            asyncio.run(_test())

    def test_horizon_too_small(self):
        with pytest.raises(Exception):
            import asyncio
            async def _test():
                from unittest.mock import AsyncMock
                mock_db = AsyncMock()
                await PredictionService.create_prediction(
                    db=mock_db,
                    user_id=1,
                    metric_name="revenue",
                    prediction_type="forecast",
                    horizon=0,
                )
            asyncio.run(_test())

    def test_valid_prediction_types(self):
        valid_types = {"revenue", "gross_profit", "dso", "ar_aging", "forecast", "anomaly_detection", "trend"}
        assert PredictionService.VALID_PREDICTION_TYPES == valid_types


class TestBuildResponse:
    """Test PredictionService.build_response formatting."""

    def test_build_response_with_values(self):
        from unittest.mock import MagicMock
        from datetime import datetime

        mock_prediction = MagicMock()
        mock_prediction.id = 1
        mock_prediction.metric_name = "revenue"
        mock_prediction.prediction_type = "forecast"
        mock_prediction.horizon = 3
        mock_prediction.predicted_values = {"2025-01": 1000, "2025-02": 1100}
        mock_prediction.confidence_interval = {"2025-01": [900, 1100]}
        mock_prediction.model_name = "Holt-Winters"
        mock_prediction.accuracy_score = 0.90  # MAPE = 10%
        mock_prediction.computed_at = datetime(2024, 1, 1)

        result = PredictionService.build_response(mock_prediction)

        assert result["id"] == 1
        assert result["metric_name"] == "revenue"
        assert result["mape"] == pytest.approx(10.0, abs=0.01)
        assert result["accepted"] is True
        assert "2025-01" in result["forecast_values"]
        assert "2025-01" in result["confidence_band"]

    def test_build_response_rejected_mape(self):
        from unittest.mock import MagicMock

        mock_prediction = MagicMock()
        mock_prediction.id = 1
        mock_prediction.metric_name = "cost"
        mock_prediction.prediction_type = "forecast"
        mock_prediction.horizon = 3
        mock_prediction.predicted_values = {}
        mock_prediction.confidence_interval = {}
        mock_prediction.model_name = "SimpleExponentialSmoothing"
        mock_prediction.accuracy_score = 0.70  # MAPE = 30%
        mock_prediction.computed_at = None

        result = PredictionService.build_response(mock_prediction)

        assert result["accepted"] is False
        assert result["rejected_reason"] is not None
        assert result["mape"] == pytest.approx(30.0, abs=0.01)
