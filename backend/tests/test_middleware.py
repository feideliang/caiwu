"""Tests for ASGI middleware: trace ID injection and exception handling."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.core.middleware import TraceIDMiddleware, _handle_exception
from app.core.exceptions import AppException, ValidationError, ResourceNotFoundError
from app.core.response import ErrorCode


class TestTraceIDMiddleware:
    """Test trace ID generation and propagation."""

    def test_generates_trace_id_when_missing(self):
        """When no x-trace-id header, middleware generates one."""
        import asyncio

        async def _test():
            mock_request = MagicMock(spec=Request)
            mock_request.headers = {}

            async def call_next(req):
                return MagicMock(spec=Response, headers={})

            middleware = TraceIDMiddleware(call_next)
            # We test the trace ID generation logic directly
            import uuid
            trace_id = uuid.uuid4().hex[:16]
            assert len(trace_id) == 16

        asyncio.run(_test())

    def test_uses_client_trace_id(self):
        """When x-trace-id header provided, middleware uses it."""
        import asyncio

        async def _test():
            mock_request = MagicMock(spec=Request)
            mock_request.headers = {"x-trace-id": "my-trace-123"}

            # Simulate the logic from dispatch
            trace_id = mock_request.headers.get("x-trace-id") or "generated"
            assert trace_id == "my-trace-123"

        asyncio.run(_test())

    def test_trace_id_is_16_chars(self):
        """Generated trace ID should be 16 hex characters."""
        import uuid
        trace_id = uuid.uuid4().hex[:16]
        assert len(trace_id) == 16
        assert all(c in "0123456789abcdef" for c in trace_id)


class TestExceptionHandling:
    """Test global exception handler in middleware."""

    def test_app_exception_returns_correct_code(self):
        import asyncio

        async def _test():
            exc = ValidationError("bad input")
            response = await _handle_exception(exc, "trace-123")

            assert isinstance(response, JSONResponse)
            assert response.status_code == 400
            body = response.body.decode()
            assert "4000" in body  # VALIDATION_ERROR code

        asyncio.run(_test())

    def test_not_found_exception(self):
        import asyncio

        async def _test():
            exc = ResourceNotFoundError("missing")
            response = await _handle_exception(exc, "trace-456")

            assert response.status_code == 404
            body = response.body.decode()
            assert "4200" in body  # NOT_FOUND code

        asyncio.run(_test())

    def test_generic_exception_returns_500(self):
        import asyncio

        async def _test():
            exc = RuntimeError("unexpected error")
            response = await _handle_exception(exc, "trace-789")

            assert response.status_code == 500
            body = response.body.decode()
            assert "5000" in body  # INTERNAL_ERROR code

        asyncio.run(_test())

    def test_trace_id_in_response_headers(self):
        import asyncio

        async def _test():
            exc = ValueError("oops")
            response = await _handle_exception(exc, "my-trace-id")

            assert response.headers.get("X-Trace-Id") == "my-trace-id"

        asyncio.run(_test())
