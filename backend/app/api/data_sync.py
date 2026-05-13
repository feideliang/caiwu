"""Data sync control endpoints (email + manual triggers)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import APIResponse, ErrorCode
from app.core.security import require_role
from app.db.session import get_db
from app.models.core import DataBatch, DataSource, DataSourceType
from app.services.email_reader import IMAPEmailReader
from app.tasks.email_poll import poll_emails_task

router = APIRouter(prefix="/data-sync", tags=["data-sync"])


def _normalize_config(value: object) -> dict:
    return value if isinstance(value, dict) else {}


@router.get("/email/batches", response_model=APIResponse)
async def list_email_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_role("admin")),
) -> APIResponse:
    stmt = select(DataBatch).order_by(DataBatch.processed_at.desc().nullslast(), DataBatch.id.desc())
    total = (await db.execute(select(func.count()).select_from(DataBatch))).scalar_one()
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    items = [
        {
            "id": row.id,
            "batch_no": row.batch_no,
            "source_id": row.source_id,
            "status": row.status.value if hasattr(row.status, "value") else row.status,
            "record_count": row.record_count,
            "file_name": row.file_name,
            "processed_at": row.processed_at.isoformat() if row.processed_at else None,
        }
        for row in result.scalars().all()
    ]
    return APIResponse.success(data={"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/email/run", response_model=APIResponse)
async def run_email_sync(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_role("admin")),
) -> APIResponse:
    _ = db
    result = poll_emails_task.apply().get()
    return APIResponse.success(data=result, message="邮件同步已执行")


@router.post("/email/test-connection", response_model=APIResponse)
async def test_email_connection(
    source_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_role("admin")),
) -> APIResponse:
    config: dict = {}
    source_name = "系统配置"
    if source_id is not None:
        source = await db.get(DataSource, source_id)
        if source is None:
            return APIResponse.error(code=ErrorCode.NOT_FOUND, message="数据源不存在")
        if source.source_type != DataSourceType.EMAIL_IMAP:
            return APIResponse.error(code=ErrorCode.VALIDATION_ERROR, message="仅支持邮件IMAP数据源")
        config = _normalize_config(source.connection_config)
        source_name = source.name

    reader = IMAPEmailReader(
        host=config.get("host"),
        port=config.get("port"),
        user=config.get("user"),
        password=config.get("password"),
        use_xoauth2=config.get("use_xoauth2"),
        max_attachment_size=config.get("max_attachment_size"),
        subject_keywords=config.get("subject_keywords"),
        from_whitelist=config.get("from_whitelist"),
    )
    reader.connect()
    reader.disconnect()
    return APIResponse.success(
        data={"source_id": source_id, "source_name": source_name, "connected": True},
        message="IMAP 连接成功",
    )


# ── BI MySQL sync endpoints ──────────────────────────────────


@router.post("/bi/mysql/run", response_model=APIResponse)
async def run_mysql_sync(
    table: str | None = Query(None),
    mode: str = Query("incremental"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_role("admin")),
) -> APIResponse:
    """Trigger MySQL → PG sync. Auto-discovers table if not specified."""
    from app.config import settings
    from app.services.bi_mysql_adapter import BIMysqlAdapter
    from app.services.data_cleaner import DataCleaner
    from app.services.data_sync import DataSyncService

    adapter = BIMysqlAdapter({
        "host": settings.bi_mysql_host,
        "port": settings.bi_mysql_port,
        "user": settings.bi_mysql_user,
        "password": settings.bi_mysql_password,
        "database": settings.bi_mysql_database,
    })

    # Discover + find table
    try:
        tables = adapter.discover_tables()
    except Exception as exc:
        return APIResponse.error(code=ErrorCode.INTERNAL_ERROR, message=f"MySQL 连接失败: {exc}")

    target = None
    if table:
        target = next((t for t in tables if t["table"] == table), None)
    else:
        target = adapter.find_target_table(tables)

    if not target:
        return APIResponse.error(code=ErrorCode.NOT_FOUND, message="未找到合适的数据表")

    # Read + map
    df_raw = adapter.fetch_data(target["table"])
    df_mapped = adapter.map_fields(df_raw)

    # Clean
    cleaner = DataCleaner()
    df_clean = cleaner.clean(df_mapped)

    # Sync
    svc = DataSyncService(db)
    if mode == "full":
        result = await svc.sync_full(df_clean, source_id=1, file_name=f"mysql_{target['table']}")
    else:
        result = await svc.sync_incremental(df_clean, source_id=1, file_name=f"mysql_{target['table']}")
    await db.commit()

    return APIResponse.success(data=result, message="MySQL 数据同步完成")


@router.post("/bi/mysql/test-connection", response_model=APIResponse)
async def test_mysql_connection(
    _admin=Depends(require_role("admin")),
) -> APIResponse:
    """Test MySQL connectivity."""
    from app.config import settings
    from app.services.bi_mysql_adapter import BIMysqlAdapter

    adapter = BIMysqlAdapter({
        "host": settings.bi_mysql_host,
        "port": settings.bi_mysql_port,
        "user": settings.bi_mysql_user,
        "password": settings.bi_mysql_password,
        "database": settings.bi_mysql_database,
    })
    result = adapter.test_connection()
    if result["status"] == "ok":
        return APIResponse.success(data=result, message="MySQL 连接成功")
    return APIResponse.error(code=ErrorCode.INTERNAL_ERROR, message=result.get("error", "连接失败"))