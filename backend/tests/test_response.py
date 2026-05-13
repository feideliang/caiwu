"""Tests for the API response envelope and exception handling."""

from __future__ import annotations

import pytest

from app.core.response import APIResponse, ErrorCode
from app.core.exceptions import (
    AppException,
    ValidationError,
    AuthenticationError,
    ForbiddenError,
    ResourceNotFoundError,
    BusinessError,
    DatabaseError,
    AppTimeoutError,
)


class TestAPIResponse:
    """Test the standard response envelope."""

    def test_success_default(self):
        resp = APIResponse.success()
        assert resp.code == 0
        assert resp.message == "ok"
        assert resp.data is None

    def test_success_with_data(self):
        resp = APIResponse.success(data={"key": "value"})
        assert resp.code == 0
        assert resp.data["key"] == "value"

    def test_success_with_trace_id(self):
        resp = APIResponse.success(data="test", trace_id="abc123")
        assert resp.trace_id == "abc123"

    def test_error_default(self):
        resp = APIResponse.error()
        assert resp.code == ErrorCode.INTERNAL_ERROR
        assert resp.message == "internal error"

    def test_error_with_code(self):
        resp = APIResponse.error(code=ErrorCode.NOT_FOUND, message="Not found")
        assert resp.code == ErrorCode.NOT_FOUND
        assert resp.message == "Not found"

    def test_model_dump_format(self):
        resp = APIResponse.success(data={"x": 1}, trace_id="t1")
        dumped = resp.model_dump(mode="json")
        assert "code" in dumped
        assert "message" in dumped
        assert "data" in dumped
        assert "trace_id" in dumped
        assert dumped["code"] == 0
        assert dumped["trace_id"] == "t1"

    def test_paginated_response(self):
        from app.core.response import PaginatedResponse
        pr = PaginatedResponse(items=[1, 2], total=2, page=1, page_size=10, total_pages=1)
        assert pr.total == 2
        assert len(pr.items) == 2


class TestExceptions:
    """Test custom exception hierarchy and status codes."""

    def test_validation_error(self):
        exc = ValidationError("bad input")
        assert exc.status_code == 400
        assert exc.code == ErrorCode.VALIDATION_ERROR

    def test_authentication_error(self):
        exc = AuthenticationError("no token")
        assert exc.status_code == 401
        assert exc.code == ErrorCode.UNAUTHENTICATED

    def test_forbidden_error(self):
        exc = ForbiddenError("wrong role")
        assert exc.status_code == 403
        assert exc.code == ErrorCode.FORBIDDEN

    def test_not_found_error(self):
        exc = ResourceNotFoundError("missing")
        assert exc.status_code == 404
        assert exc.code == ErrorCode.NOT_FOUND

    def test_business_error(self):
        exc = BusinessError("logic failed")
        assert exc.status_code == 400
        assert exc.code == ErrorCode.BUSINESS_ERROR

    def test_database_error(self):
        exc = DatabaseError("db down")
        assert exc.status_code == 500
        assert exc.code == ErrorCode.DATABASE_ERROR

    def test_timeout_error(self):
        exc = AppTimeoutError("timed out")
        assert exc.status_code == 504
        assert exc.code == ErrorCode.TIMEOUT_ERROR

    def test_custom_code_override(self):
        exc = AppException("custom", code=9999, status_code=418)
        assert exc.code == 9999
        assert exc.status_code == 418


class TestErrorCodeConstants:
    """Verify error code values are stable."""

    def test_success_is_zero(self):
        assert ErrorCode.SUCCESS == 0

    def test_4xxx_range(self):
        assert ErrorCode.VALIDATION_ERROR == 4000
        assert ErrorCode.UNAUTHENTICATED == 4010
        assert ErrorCode.FORBIDDEN == 4030
        assert ErrorCode.NOT_FOUND == 4200

    def test_5xxx_range(self):
        assert ErrorCode.INTERNAL_ERROR == 5000
        assert ErrorCode.DATABASE_ERROR == 5001
        assert ErrorCode.TIMEOUT_ERROR == 5003
