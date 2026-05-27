"""ASGI middleware: trace ID injection, global exception handling."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.core.exceptions import AppException
from app.core.response import APIResponse, ErrorCode


_TRACE_ID_HEADER = "X-Trace-Id"


class TraceIDMiddleware:
    """Native ASGI middleware: attach a unique X-Trace-Id to every request and response.

    This replaces the legacy BaseHTTPMiddleware implementation which had
    performance overhead due to body buffering and anyio task group usage.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Extract or generate trace ID
        headers = dict(scope.get("headers", []))
        trace_id_bytes = headers.get(b"x-trace-id")
        trace_id = trace_id_bytes.decode() if trace_id_bytes else uuid.uuid4().hex[:16]

        # Inject trace_id into scope state
        scope["state"] = {"trace_id": trace_id}

        async def send_with_trace_id(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                # Add trace ID header to response
                headers = list(message.get("headers", []))
                headers.append((b"x-trace-id", trace_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_trace_id)
        except Exception as exc:
            response = await _handle_exception(exc, trace_id)
            await response(scope, receive, send)


async def _handle_exception(exc: Exception, trace_id: str) -> JSONResponse:
    """Convert any unhandled exception into a safe JSON error response."""

    if isinstance(exc, AppException):
        status = exc.status_code
        body = APIResponse.error(code=exc.code, message=str(exc), trace_id=trace_id)
    else:
        status = 500
        msg = "internal server error" if not settings.debug else str(exc)
        body = APIResponse.error(code=ErrorCode.INTERNAL_ERROR, message=msg, trace_id=trace_id)

    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json"),
        headers={_TRACE_ID_HEADER: trace_id},
    )
