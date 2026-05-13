"""Celery task for time-series prediction."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_sync_db():
    """Return a synchronous SQLAlchemy session for use inside Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings

    engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine)()


@celery_app.task(
    name="prediction.run_prediction",
    queue="prediction",
    bind=True,
    acks_late=True,
    max_retries=2,
    default_retry_delay=30,
)
def run_prediction_task(self, prediction_id: int) -> dict:
    """Execute a prediction task using Holt-Winters / ExponentialSmoothing.

    Returns forecast values with confidence intervals and MAPE quality gate.
    """
    logger.info("Starting prediction: prediction_id=%s", prediction_id)

    try:
        result = _run_forecast(prediction_id)

        # Save result to prediction_result table
        session = _get_sync_db()
        try:
            from app.models.v3 import PredictionResult

            obj = session.query(PredictionResult).filter(PredictionResult.id == prediction_id).first()
            if obj:
                obj.predicted_values = result["forecast_values"]
                obj.confidence_interval = result["confidence_interval"]
                obj.model_name = result["model_type"]
                obj.accuracy_score = 1.0 - result["mape"] / 100.0 if result["mape"] else None
                obj.computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                session.commit()
        finally:
            session.close()

        logger.info("Prediction completed: prediction_id=%s mape=%s", prediction_id, result["mape"])
        return result

    except Exception as exc:
        logger.exception("Prediction failed: prediction_id=%s", prediction_id)
        # Update error status
        session = _get_sync_db()
        try:
            from app.models.v3 import PredictionResult

            obj = session.query(PredictionResult).filter(PredictionResult.id == prediction_id).first()
            if obj:
                obj.model_name = "error"
                obj.accuracy_score = 0.0
                session.commit()
        finally:
            session.close()

        retry_count = self.request.retries
        if retry_count < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (2 ** retry_count))
        raise


def _run_forecast(prediction_id: int) -> dict:
    """Run the actual forecasting logic."""
    from app.config import settings

    session = _get_sync_db()
    try:
        from app.models.v3 import PredictionResult
        from app.models.core import FinancialData

        from sqlalchemy import select

        obj = session.query(PredictionResult).filter(PredictionResult.id == prediction_id).first()
        if not obj:
            raise ValueError(f"PredictionResult {prediction_id} not found")

        metric_name = obj.metric_name
        prediction_type = obj.prediction_type or "forecast"
        horizon = obj.horizon or 3

        # Fetch historical data
        stmt = (
            select(FinancialData.metric_value, FinancialData.period)
            .where(FinancialData.metric_name == metric_name)
            .order_by(FinancialData.period)
        )
        rows = session.execute(stmt).all()

        if len(rows) < settings.prediction_min_history_months:
            obj.model_name = "insufficient_data"
            obj.accuracy_score = None
            obj.computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            session.commit()
            return {
                "prediction_id": prediction_id,
                "forecast_values": {},
                "confidence_interval": {},
                "model_type": "insufficient_data",
                "training_window": len(rows),
                "mape": None,
                "accepted": False,
                "rejected_reason": f"数据不足：需要至少 {settings.prediction_min_history_months} 期历史数据，当前仅 {len(rows)} 期",
            }

        values = [float(r.metric_value) for r in rows]
        periods = [r.period for r in rows]

        # Run the model
        model_type, forecast_values, confidence_interval, mape = _fit_model(
            values, horizon, prediction_type
        )

        # Build forecast period labels
        last_period = periods[-1] if periods else "unknown"
        forecast_periods = _next_periods(last_period, horizon)

        forecast_dict = {p: v for p, v in zip(forecast_periods, forecast_values)}
        confidence_dict = {p: ci for p, ci in zip(forecast_periods, confidence_interval)}

        # Quality gate
        accepted, reason = _quality_gate(mape)

        return {
            "prediction_id": prediction_id,
            "forecast_values": forecast_dict,
            "confidence_interval": confidence_dict,
            "model_type": model_type,
            "training_window": len(values),
            "mape": round(mape, 4),
            "accepted": accepted,
            "rejected_reason": reason if not accepted else None,
        }
    finally:
        session.close()


def _fit_model(values: list[float], horizon: int, prediction_type: str) -> tuple:
    """Fit a time-series model and return (model_type, forecast, confidence, mape).

    Tries statsmodels Holt-Winters first; falls back to ExponentialSmoothing
    or simple exponential smoothing.
    """
    import math

    # Try statsmodels
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        # Determine seasonal period based on data length
        n = len(values)
        seasonal_period = 12 if n >= 24 else None

        if seasonal_period and n >= 2 * seasonal_period:
            model = ExponentialSmoothing(
                values,
                trend="add",
                seasonal="add",
                seasonal_periods=seasonal_period,
            ).fit()
            model_type = "Holt-Winters"
        else:
            model = ExponentialSmoothing(
                values,
                trend="add",
            ).fit()
            model_type = "ExponentialSmoothing"

        forecast = model.forecast(horizon)
        forecast_values = forecast.tolist()

        # Compute in-sample MAPE
        fitted = model.fittedvalues
        mape = _compute_mape(values[-len(fitted) :], fitted.tolist())

        # Confidence intervals via residual std * z-score (95%)
        residuals = [v - f for v, f in zip(values[-len(fitted) :], fitted.tolist())]
        if residuals:
            std = math.sqrt(sum(r ** 2 for r in residuals) / len(residuals))
            z = 1.96  # 95% CI
            confidence = [[round(v - z * std, 4), round(v + z * std, 4)] for v in forecast_values]
        else:
            confidence = [[v * 0.9, v * 1.1] for v in forecast_values]

        return model_type, forecast_values, confidence, mape

    except ImportError:
        # Fallback: simple exponential smoothing
        logger.warning("statsmodels not available; using simple exponential smoothing")
        alpha = 0.3
        smoothed = [values[0]]
        for v in values[1:]:
            smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])

        last = smoothed[-1]
        forecast_values = [last] * horizon
        mape = _compute_mape(values, smoothed)

        # Approximate CI
        residuals = [v - s for v, s in zip(values, smoothed)]
        std = math.sqrt(sum(r ** 2 for r in residuals) / len(residuals)) if residuals else last * 0.1
        z = 1.96
        confidence = [[round(v - z * std, 4), round(v + z * std, 4)] for v in forecast_values]

        return "SimpleExponentialSmoothing", forecast_values, confidence, mape


def _compute_mape(actual: list[float], predicted: list[float]) -> float:
    """Compute Mean Absolute Percentage Error."""
    if not actual or not predicted:
        return 100.0
    n = min(len(actual), len(predicted))
    errors = []
    for i in range(n):
        if actual[i] != 0:
            errors.append(abs((actual[i] - predicted[i]) / actual[i]) * 100)
    return sum(errors) / len(errors) if errors else 0.0


def _quality_gate(mape: float) -> tuple[bool, str | None]:
    """Evaluate MAPE against quality gates."""
    from app.config import settings

    if mape < settings.prediction_mape_qualified:
        return True, None
    elif mape < settings.prediction_mape_warning:
        return True, "MAPE 处于警告区间（15-25%），建议复核"
    else:
        return False, f"MAPE {mape:.2f}% 超过阈值（{settings.prediction_mape_warning}%），模型被拒绝"


def _next_periods(last_period: str, n: int) -> list[str]:
    """Generate the next n period labels after the last one."""
    import re

    # Try YYYY-MM format
    m = re.match(r"(\d{4})-(\d{2})", last_period)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        periods = []
        for i in range(1, n + 1):
            m2 = month + i
            y2 = year + (m2 - 1) // 12
            m2 = (m2 - 1) % 12 + 1
            periods.append(f"{y2}-{m2:02d}")
        return periods

    # Try YYYY-Qn format
    m = re.match(r"(\d{4})-Q([1-4])", last_period)
    if m:
        year, quarter = int(m.group(1)), int(m.group(2))
        periods = []
        for i in range(1, n + 1):
            q2 = quarter + i
            y2 = year + (q2 - 1) // 4
            q2 = (q2 - 1) % 4 + 1
            periods.append(f"{y2}-Q{q2}")
        return periods

    # Fallback: append index
    return [f"{last_period}_+{i}" for i in range(1, n + 1)]
