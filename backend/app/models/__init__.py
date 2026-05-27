# models/__init__.py

from app.models.core import (FinancialData, DataBatch, DataSource, DataQualityLog,
                              ChartConfig, DashboardLayout, UserPreference,
                              SystemConfig, SyncJob, KnowledgeRule, IncomeMarginDetail)
from app.models.dimensions import DimCustomer, DimProduct, DimOrganization, DimProject
from app.models.v3 import Insight, FilterView, CorrelationResult, CorrelationCalibration
from app.models.v3 import PredictionResult, ReportTask
from app.models.v4 import AuditLog, Notification, User, Role

__all__ = [
    # Original (9)
    "FinancialData",
    "DataBatch",
    "DataSource",
    "DataQualityLog",
    "ChartConfig",
    "DashboardLayout",
    "UserPreference",
    "SystemConfig",
    "SyncJob",
    "KnowledgeRule",
    "IncomeMarginDetail",
    "DimCustomer",
    "DimProduct",
    "DimOrganization",
    "DimProject",
    # V3.0 (6)
    "Insight",
    "FilterView",
    "CorrelationResult",
    "CorrelationCalibration",
    "PredictionResult",
    "ReportTask",
    # V4.0 (4)
    "AuditLog",
    "Notification",
    "User",
    "Role",
]
