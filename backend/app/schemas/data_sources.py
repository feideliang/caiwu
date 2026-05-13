"""Data sources CRUD schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DataSourceCreate(BaseModel):
    name: str
    source_type: str = "email_imap"
    connection_config: Optional[dict] = None
    priority: int = 0


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    source_type: Optional[str] = None
    connection_config: Optional[dict] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class DataSourceRead(BaseModel):
    id: int
    name: str
    source_type: str
    connection_config: Optional[dict] = None
    is_active: bool
    priority: int
    last_sync_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
