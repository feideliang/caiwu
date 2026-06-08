"""Prediction service — orchestrates forecast task creation and result retrieval."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, ResourceNotFoundError
from app.models.v3 import PredictionResult

logger = logging.getLogger(__name__)

# Check if Celery is available — only use it if a worker is confirmed running.
# We default to synchronous execution since the Celery import may succeed but
# no worker may be listening on the queue.
CELERY_AVAILABLE = False


class PredictionService:
    """Service for managing prediction tasks."""

    VALID_PREDICTION_TYPES = {"revenue", "gross_profit", "dso", "ar_aging", "forecast", "anomaly_detection", "trend"}

    @staticmethod
    async def create_prediction(
        db: AsyncSession,
        user_id: int,
        metric_name: str,
        prediction_type: str = "forecast",
        horizon: int = 3,
    ) -> PredictionResult:
        """Create a new prediction task. If Celery is available, dispatch async; otherwise run synchronously."""

        if prediction_type not in PredictionService.VALID_PREDICTION_TYPES:
            raise BusinessError(
                f"Invalid prediction type '{prediction_type}'. "
                f"Allowed: {PredictionService.VALID_PREDICTION_TYPES}"
            )

        if horizon < 1 or horizon > 12:
            raise BusinessError("Horizon must be between 1 and 12 periods")

        prediction = PredictionResult(
            metric_name=metric_name,
            prediction_type=prediction_type,
            horizon=horizon,
            predicted_values={},
            confidence_interval=None,
            model_name=None,
            accuracy_score=None,
            computed_at=None,
        )
        db.add(prediction)
        await db.flush()
        await db.refresh(prediction)

        if CELERY_AVAILABLE:
            # Dispatch Celery task
            celery_result = run_prediction_task.delay(prediction.id)
            logger.info("Prediction task created: id=%d celery_id=%s", prediction.id, celery_result.id)
        else:
            # Run prediction synchronously using async db session
            from app.models.core import AggPeriodSummary
            from app.config import settings

            logger.info("Running prediction synchronously: id=%d", prediction.id)

            # Fetch historical data from AggPeriodSummary
            metric_col_map = {
                "revenue": "revenue",
                "cost": "cost",
                "gross_profit": "gross_profit",
                "target_revenue": "target_revenue",
            }
            col_name = metric_col_map.get(metric_name)
            if col_name is None:
                # Unknown metric: no data source available
                prediction.accuracy_score = None
                prediction.model_name = "insufficient_data"
                prediction.computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                prediction._insufficient_data_message = f"不支持的预测指标：{metric_name}"
                await db.flush()
                return prediction

            if col_name == "ALL":
                # Not a real column, handle gracefully
                prediction.accuracy_score = None
                prediction.model_name = "insufficient_data"
                prediction.computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await db.flush()
                return prediction

            # Aggregate across all departments (no per-company "ALL" rows in AggPeriodSummary)
            stmt = (
                select(
                    func.sum(getattr(AggPeriodSummary, col_name)),
                    AggPeriodSummary.period,
                )
                .where(AggPeriodSummary.bgbu != "ALL")
                .group_by(AggPeriodSummary.period)
                .order_by(AggPeriodSummary.period)
            )
            rows = (await db.execute(stmt)).all()

            if len(rows) < settings.prediction_min_history_months:
                prediction.accuracy_score = None
                prediction.model_name = "insufficient_data"
                prediction.computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                prediction._insufficient_data_message = (
                    f"数据不足：需要至少 {settings.prediction_min_history_months} 期历史数据，"
                    f"当前仅 {len(rows)} 期"
                )
                await db.flush()
                return prediction

            values = [float(r[0]) for r in rows]
            periods = [r[1] for r in rows]

            # Try to import and run the model
            try:
                from app.tasks.prediction import _fit_model, _next_periods
                model_type, forecast_values, confidence_interval, mape = _fit_model(
                    values, horizon, prediction_type
                )
                last_period = periods[-1] if periods else "unknown"
                forecast_periods = _next_periods(last_period, horizon)

                forecast_dict = {p: round(v, 2) for p, v in zip(forecast_periods, forecast_values)}
                confidence_dict = {}
                for p, ci in zip(forecast_periods, confidence_interval):
                    if isinstance(ci, (list, tuple)) and len(ci) >= 2:
                        confidence_dict[p] = [round(ci[0], 2), round(ci[1], 2)]

                prediction.predicted_values = forecast_dict
                prediction.confidence_interval = confidence_dict
                prediction.model_name = model_type
                prediction.accuracy_score = mape
            except Exception as e:
                logger.warning("Prediction model failed: %s", e, exc_info=True)
                prediction.model_name = "fallback_simple"
                # Simple fallback: last value repeated
                last_val = values[-1] if values else 0
                from app.tasks.prediction import _next_periods
                last_period = periods[-1] if periods else "unknown"
                forecast_periods = _next_periods(last_period, horizon)
                forecast_dict = {p: round(last_val, 2) for p in forecast_periods}
                prediction.predicted_values = forecast_dict
                prediction.accuracy_score = None

            prediction.computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.flush()
            await db.refresh(prediction)
            logger.info("Prediction completed synchronously: id=%d", prediction.id)

        return prediction

    @staticmethod
    async def get_prediction(
        db: AsyncSession,
        prediction_id: int,
    ) -> PredictionResult:
        """Get a single prediction result."""
        stmt = select(PredictionResult).where(PredictionResult.id == prediction_id)
        result = await db.execute(stmt)
        prediction = result.scalar_one_or_none()
        if not prediction:
            raise ResourceNotFoundError(f"Prediction {prediction_id} not found")
        return prediction

    @staticmethod
    async def build_response(prediction: PredictionResult, db: AsyncSession | None = None) -> dict:
        """Build the API response dict from a PredictionResult ORM object."""

        forecast_values = prediction.predicted_values or {}
        confidence_interval = prediction.confidence_interval or {}

        # Transform confidence interval into band format
        confidence_band = {}
        for period, band in confidence_interval.items():
            if isinstance(band, list) and len(band) >= 2:
                confidence_band[period] = {"lower": band[0], "upper": band[1]}
            else:
                confidence_band[period] = {"lower": None, "upper": None}

        # Quality gate evaluation
        mape = prediction.accuracy_score
        mape_pct = (1.0 - mape) * 100 if mape is not None else None

        accepted = True
        rejected_reason = None
        if mape_pct is not None:
            if mape_pct > 25:
                accepted = False
                rejected_reason = f"MAPE {mape_pct:.2f}% 超过阈值（25%），模型被拒绝"
            elif mape_pct > 15:
                accepted = True
                rejected_reason = f"MAPE {mape_pct:.2f}% 处于警告区间（15-25%），建议复核"

        # Fetch historical values for chart context from AggPeriodSummary
        historical_values = {}
        if db is not None:
            from app.models.core import AggPeriodSummary

            metric_col_map = {
                "revenue": AggPeriodSummary.revenue,
                "cost": AggPeriodSummary.cost,
                "gross_profit": AggPeriodSummary.gross_profit,
                "target_revenue": AggPeriodSummary.target_revenue,
            }
            agg_col = metric_col_map.get(prediction.metric_name)
            if agg_col is not None:
                # Aggregate across all departments (no per-company "ALL" rows)
                stmt = (
                    select(AggPeriodSummary.period, func.sum(agg_col))
                    .where(AggPeriodSummary.bgbu != "ALL")
                    .group_by(AggPeriodSummary.period)
                    .order_by(AggPeriodSummary.period)
                )
                rows = (await db.execute(stmt)).all()
                for period, value in rows:
                    if value:
                        historical_values[str(period)] = round(float(value), 2)

        # Build message for insufficient data
        insufficient_msg = getattr(prediction, '_insufficient_data_message', None) or None
        if prediction.model_name == "insufficient_data" and not insufficient_msg:
            from app.config import settings
            insufficient_msg = f"数据不足：需要至少 {settings.prediction_min_history_months} 期历史数据"

        return {
            "id": prediction.id,
            "metric_name": prediction.metric_name,
            "prediction_type": prediction.prediction_type,
            "horizon": prediction.horizon,
            "forecast_values": forecast_values,
            "confidence_band": confidence_band,
            "historical_values": historical_values,
            "model_type": prediction.model_name,
            "training_window": None,  # Would need to track in model
            "mape": round(mape_pct, 4) if mape_pct is not None else None,
            "accuracy_score": prediction.accuracy_score,
            "accepted": accepted,
            "rejected_reason": rejected_reason,
            "message": insufficient_msg,
            "computed_at": prediction.computed_at.isoformat() if prediction.computed_at else None,
        }
