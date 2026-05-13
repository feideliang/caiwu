"""Shared DAO layer with Redis cache-aside support."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.core.cache import cache_get, cache_set, cache_delete_pattern, DEFAULT_TTL
from app.models.core import Base


# ── Generic CRUD DAO ─────────────────────────────────────────

class BaseDAO:
    """Base Data Access Object with optional caching."""

    model: type[Base] | None = None
    cache_prefix: str = "dao"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _cache_key(self, suffix: str) -> str:
        return f"{self.cache_prefix}:{self.model.__tablename__}:{suffix}" if self.model else f"{self.cache_prefix}:{suffix}"

    async def get_by_id(self, record_id: int, bypass_cache: bool = False) -> Any | None:
        if not bypass_cache:
            cached = await cache_get(self._cache_key(f"id:{record_id}"))
            if cached is not None:
                return cached

        stmt = select(self.model).where(self.model.id == record_id)  # type: ignore[union-attr]
        result = await self.db.execute(stmt)
        obj = result.scalar_one_or_none()

        if obj is not None:
            await cache_set(self._cache_key(f"id:{record_id}"), _to_dict(obj))
        return obj

    async def list(
        self,
        filters: list[dict] | None = None,
        sort: list[dict] | None = None,
        page: int = 1,
        page_size: int = 20,
        bypass_cache: bool = False,
    ) -> tuple[list[dict], int]:
        """Return (items, total_count)."""
        cache_key = self._cache_key(f"list:{page}:{page_size}:{str(filters)}")

        if not bypass_cache:
            cached = await cache_get(cache_key)
            if cached is not None:
                return cached["items"], cached["total"]

        stmt = select(self.model)  # type: ignore[union-attr]
        stmt = self._apply_filters(stmt, filters)
        stmt = self._apply_sort(stmt, sort)

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        # Paginate
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        objects = result.scalars().all()

        items = [_to_dict(o) for o in objects]
        payload = {"items": items, "total": total}

        await cache_set(cache_key, payload, DEFAULT_TTL)
        return items, total

    async def create(self, data: dict[str, Any]) -> Any:
        obj = self.model(**data)  # type: ignore[misc]
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        await self._invalidate_list_cache()
        return obj

    async def update(self, record_id: int, data: dict[str, Any]) -> Any | None:
        obj = await self.get_by_id(record_id, bypass_cache=True)
        if obj is None:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        await self.db.flush()
        await self.db.refresh(obj)
        await cache_delete_pattern(self._cache_key("*"))
        return obj

    async def delete(self, record_id: int) -> bool:
        obj = await self.get_by_id(record_id, bypass_cache=True)
        if obj is None:
            return False
        await self.db.delete(obj)
        await self.db.flush()
        await cache_delete_pattern(self._cache_key("*"))
        return True

    async def execute_query(self, stmt: Select, bypass_cache: bool = False) -> list[dict]:
        """Execute an arbitrary SELECT and return rows as dicts."""
        result = await self.db.execute(stmt)
        return [dict(r._mapping) for r in result.mappings().all()]

    # ── Internal helpers ──────────────────────────────────────

    def _apply_filters(self, stmt: Select, filters: list[dict] | None) -> Select:
        if not filters:
            return stmt
        for f in filters:
            field = f.get("field")
            op = f.get("operator")
            value = f.get("value")
            if not field or not hasattr(self.model, field):  # type: ignore[union-attr]
                continue
            col = getattr(self.model, field)
            if op == "eq":
                stmt = stmt.where(col == value)
            elif op == "ne":
                stmt = stmt.where(col != value)
            elif op == "gt":
                stmt = stmt.where(col > value)
            elif op == "gte":
                stmt = stmt.where(col >= value)
            elif op == "lt":
                stmt = stmt.where(col < value)
            elif op == "lte":
                stmt = stmt.where(col <= value)
            elif op == "in":
                stmt = stmt.where(col.in_(value))
            elif op == "like":
                stmt = stmt.where(col.like(f"%{value}%"))
        return stmt

    def _apply_sort(self, stmt: Select, sort: list[dict] | None) -> Select:
        from sqlalchemy import desc

        if not sort:
            return stmt
        for s in sort:
            field = s.get("field")
            order = s.get("order", "asc")
            if not field or not hasattr(self.model, field):  # type: ignore[union-attr]
                continue
            col = getattr(self.model, field)
            stmt = stmt.order_by(desc(col) if order == "desc" else col)
        return stmt

    async def _invalidate_list_cache(self) -> None:
        if self.model:
            await cache_delete_pattern(f"{self.cache_prefix}:{self.model.__tablename__}:*")


def _to_dict(obj: Any) -> dict:
    """Convert a SQLAlchemy ORM object to a plain dict."""
    data = {}
    for col in obj.__table__.columns:  # type: ignore[union-attr]
        val = getattr(obj, col.name)
        if val is not None:
            data[col.name] = val
        else:
            data[col.name] = None
    return data


# ── Concrete DAOs ─────────────────────────────────────────────

from app.models.core import (
    ChartConfig,
    DashboardLayout,
    DataBatch,
    DataQualityLog,
    DataSource,
    FinancialData,
    SystemConfig,
    SyncJob,
    UserPreference,
)
from app.models.v3 import (
    CorrelationCalibration,
    CorrelationResult,
    Insight,
    FilterView,
    PredictionResult,
    ReportTask,
)
from app.models.v4 import AuditLog, Notification, Role, User


class FinancialDataDAO(BaseDAO):
    model = FinancialData
    cache_prefix = "dao"


class InsightDAO(BaseDAO):
    model = Insight
    cache_prefix = "dao"


class DashboardLayoutDAO(BaseDAO):
    model = DashboardLayout
    cache_prefix = "dao"


class UserDAO(BaseDAO):
    model = User
    cache_prefix = "dao"


class RoleDAO(BaseDAO):
    model = Role
    cache_prefix = "dao"


class SyncJobDAO(BaseDAO):
    model = SyncJob
    cache_prefix = "dao"


class PredictionResultDAO(BaseDAO):
    model = PredictionResult
    cache_prefix = "dao"


class ReportTaskDAO(BaseDAO):
    model = ReportTask
    cache_prefix = "dao"


class AuditLogDAO(BaseDAO):
    model = AuditLog
    cache_prefix = "dao"


class NotificationDAO(BaseDAO):
    model = Notification
    cache_prefix = "dao"
