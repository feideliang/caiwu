"""Excel upload API — reuses the same parse → clean → sync pipeline as email_poll."""
from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import APIResponse
from app.core.security import require_role
from app.db.session import get_db
from app.services.data_cleaner import DataCleaner
from app.services.data_sync import DataSyncService
from app.services.excel_parser import ExcelParser

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/excel", response_model=APIResponse)
async def upload_excel(
    file: UploadFile = File(...),
    source_id: int | None = Form(None),
    sync_mode: str = Form("incremental"),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_role("admin", "analyst")),
) -> APIResponse:
    if not file.filename or not (file.filename.endswith(".xlsx") or file.filename.endswith(".xls")):
        return APIResponse.error(code=400, message="仅支持 .xlsx / .xls 文件")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        return APIResponse.error(code=413, message="文件超过 50MB 限制")

    fd, path = tempfile.mkstemp(suffix=os.path.splitext(file.filename)[1])
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(content)

        parse_result = ExcelParser().parse(path)
        if parse_result.dataframe.empty:
            return APIResponse.error(code=400, message="无法解析文件内容或文件为空")

        clean_result = DataCleaner().clean(parse_result.dataframe)

        sync_service = DataSyncService(db)
        if sync_mode == "full":
            sync_result = await sync_service.sync_full(
                clean_result.dataframe, source_id=source_id, file_name=file.filename,
            )
        else:
            sync_result = await sync_service.sync_incremental(
                clean_result.dataframe, source_id=source_id, file_name=file.filename,
            )
        await db.commit()

        return APIResponse.success(data={
            "filename": file.filename,
            "rows_parsed": parse_result.row_count,
            "rows_cleaned": clean_result.cleaned_row_count,
            "rows_synced": sync_result.get("rows_upserted") or sync_result.get("rows_loaded", 0),
            "batch_id": sync_result.get("batch_id"),
            "status": sync_result.get("status"),
            "errors": sync_result.get("errors", [])[:10],
        })
    finally:
        if os.path.exists(path):
            os.unlink(path)
