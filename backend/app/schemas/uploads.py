"""Upload schemas."""
from __future__ import annotations

from pydantic import BaseModel


class UploadExcelResponse(BaseModel):
    filename: str
    rows_parsed: int = 0
    rows_cleaned: int = 0
    rows_synced: int = 0
    batch_id: int | None = None
    errors: list[str] = []
