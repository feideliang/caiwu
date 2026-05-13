"""ASGI middleware: trace ID injection, global exception handling."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.core.exceptions import AppException
from app.core.response import APIResponse, ErrorCode


_TRACE_ID_HEADER = "X-Trace-Id"


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique X-Trace-Id to every request and response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex[:16]
        request.state.trace_id = trace_id

        try:
            response = await call_next(request)
        except Exception as exc:
            return await _handle_exception(exc, trace_id)

        response.headers[_TRACE_ID_HEADER] = trace_id
        return response


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
