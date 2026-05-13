"""Prediction API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError
from app.core.response import APIResponse, ErrorCode
from app.core.security import get_current_user, TokenPayload
from app.db.session import get_db
from app.schemas.predictions import PredictionCreateRequest, PredictionResultResponse
from app.services.prediction_service import PredictionService, CELERY_AVAILABLE

router = APIRouter(prefix="/predictions", tags=["predictions"])
logger = logging.getLogger(__name__)


@router.post("", response_model=APIResponse, status_code=201)
async def create_prediction(
    body: PredictionCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Create a new prediction task.

    Minimum 12 months of historical data required.
    The task runs asynchronously via Celery.
    """
    try:
        prediction = await PredictionService.create_prediction(
            db=db,
            user_id=int(user.sub),
            metric_name=body.metric_name,
            prediction_type=body.prediction_type,
            horizon=body.horizon,
        )
        result = await PredictionService.build_response(prediction, db)
        status = "processing" if CELERY_AVAILABLE else "completed"
        result["status"] = status
        return APIResponse.success(
            data=result,
            message="Prediction task created" if CELERY_AVAILABLE else "Prediction completed",
        )
    except BusinessError as exc:
        return APIResponse.error(code=exc.code, message=str(exc))


@router.get("/{prediction_id}", response_model=APIResponse)
async def get_prediction(
    prediction_id: int,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> APIResponse:
    """Get prediction result by ID.

    Returns forecast values, confidence bands, model type, MAPE, and acceptance status.
    """
    prediction = await PredictionService.get_prediction(db, prediction_id)
    result = await PredictionService.build_response(prediction, db)
    return APIResponse.success(data=result)
