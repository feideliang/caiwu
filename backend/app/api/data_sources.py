"""Data sources CRUD API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.core.response import APIResponse, ErrorCode
from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.core import DataSource
from app.schemas.data_sources import DataSourceCreate, DataSourceRead, DataSourceUpdate

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


@router.post("", response_model=APIResponse)
async def create_data_source(
    body: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_role("admin")),
) -> APIResponse:
    existing = await db.execute(select(DataSource).where(DataSource.name == body.name))
    if existing.scalar_one_or_none():
        return APIResponse.error(code=ErrorCode.ALREADY_EXISTS, message="数据源名称已存在")
    ds = DataSource(name=body.name, source_type=body.source_type,
                    connection_config=body.connection_config or {}, priority=body.priority)
    db.add(ds)
    await db.flush()
    return APIResponse.success(data={"id": ds.id})


@router.get("", response_model=APIResponse)
async def list_data_sources(
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    stmt = select(DataSource)
    if is_active is not None:
        stmt = stmt.where(DataSource.is_active == is_active)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size).order_by(DataSource.priority)
    result = await db.execute(stmt)
    items = [DataSourceRead.model_validate(r) for r in result.scalars().all()]
    return APIResponse.success(data={"items": [i.model_dump() for i in items], "total": total, "page": page, "page_size": page_size})


@router.get("/{ds_id}", response_model=APIResponse)
async def get_data_source(
    ds_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> APIResponse:
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise ResourceNotFoundError("数据源不存在")
    return APIResponse.success(data=DataSourceRead.model_validate(ds).model_dump())


@router.put("/{ds_id}", response_model=APIResponse)
async def update_data_source(
    ds_id: int,
    body: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_role("admin")),
) -> APIResponse:
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise ResourceNotFoundError("数据源不存在")
    update_data = body.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(ds, k, v)
    await db.flush()
    return APIResponse.success(message="已更新")


@router.delete("/{ds_id}", response_model=APIResponse)
async def delete_data_source(
    ds_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_role("admin")),
) -> APIResponse:
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise ResourceNotFoundError("数据源不存在")
    ds.is_active = False
    await db.flush()
    return APIResponse.success(message="已停用")
