"""Unified API response envelope and error codes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Standard error codes ──────────────────────────────────────

class ErrorCode:
    """Canonical error code constants grouped by category."""

    # 2xx – Success
    SUCCESS = 0

    # 4xxx – Validation / client errors
    VALIDATION_ERROR = 4000
    MISSING_FIELD = 4001
    INVALID_FORMAT = 4002
    UNAUTHENTICATED = 4010
    FORBIDDEN = 4030

    # 42xx – Resource errors
    NOT_FOUND = 4200
    CONFLICT = 4201
    ALREADY_EXISTS = 4202

    # 43xx – Business logic errors
    BUSINESS_ERROR = 4300
    DATA_QUALITY_CHECK_FAILED = 4301
    SYNC_FAILED = 4302
    REPORT_GENERATION_FAILED = 4303

    # 5xxx – Server errors
    INTERNAL_ERROR = 5000
    DATABASE_ERROR = 5001
    EXTERNAL_SERVICE_ERROR = 5002
    TIMEOUT_ERROR = 5003


# ── Response envelope ─────────────────────────────────────────

class APIResponse(BaseModel):
    """Standard response envelope used by every endpoint."""

    code: int = Field(default=ErrorCode.SUCCESS, description="Business error code; 0 = success")
    message: str = Field(default="ok", description="Human-readable status message")
    data: Any = Field(default=None, description="Response payload")
    trace_id: str = Field(default="", description="Request trace ID for log correlation")

    @classmethod
    def success(cls, data: Any = None, message: str = "ok", trace_id: str = "") -> "APIResponse":
        return cls(code=ErrorCode.SUCCESS, message=message, data=data, trace_id=trace_id)

    @classmethod
    def error(
        cls,
        code: int = ErrorCode.INTERNAL_ERROR,
        message: str = "internal error",
        data: Any = None,
        trace_id: str = "",
    ) -> "APIResponse":
        return cls(code=code, message=message, data=data, trace_id=trace_id)


class PaginatedResponse(BaseModel):
    """Paginated wrapper for list endpoints."""

    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
