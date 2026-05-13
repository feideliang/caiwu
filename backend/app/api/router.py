"""Main API router — mounts all v1 sub-routers under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.auth import router as auth_router, admin_router
from app.api.dashboard import router as dashboard_router
from app.api.query import router as query_router
from app.api.reports import router as reports_router
from app.api.predictions import router as predictions_router
from app.api.notifications import router as notifications_router
from app.api.ai import router as ai_router
from app.api.insights import router as insights_router
from app.api.filters import router as filters_router
from app.api.correlations import router as correlations_router
from app.api.drilldowns import router as drilldowns_router
from app.api.audit import router as audit_router
from app.api.system import router as system_router
from app.api.transactions import router as transactions_router
from app.api.data_sources import router as data_sources_router
from app.api.data_quality import router as data_quality_router
from app.api.data_sync import router as data_sync_router
from app.api.uploads import router as uploads_router
from app.api.metrics import router as metrics_router
from app.api.rules import router as rules_router

api_v1_router = APIRouter(prefix="/api/v1")

# Mount sub-routers (routers already carry their own prefix: /auth, /dashboard, etc.)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(query_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(predictions_router)
api_v1_router.include_router(notifications_router)
api_v1_router.include_router(ai_router)
api_v1_router.include_router(insights_router)
api_v1_router.include_router(filters_router)
api_v1_router.include_router(correlations_router)
api_v1_router.include_router(drilldowns_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(system_router)
api_v1_router.include_router(transactions_router)
api_v1_router.include_router(data_sources_router)
api_v1_router.include_router(data_quality_router)
api_v1_router.include_router(data_sync_router)
api_v1_router.include_router(uploads_router)
api_v1_router.include_router(metrics_router)
api_v1_router.include_router(rules_router)
