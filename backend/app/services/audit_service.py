"""Audit logging service — decorator and utility for capturing write-operation audit trails."""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.v4 import AuditLog


async def log_audit(
    db: AsyncSession,
    user_id: int | None,
    action: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    before_value: dict | None = None,
    after_value: dict | None = None,
    ip_address: str | None = None,
    trace_id: str | None = None,
) -> None:
    """Insert an audit log record."""
    detail: dict[str, Any] = {}
    if before_value is not None:
        detail["before"] = before_value
    if after_value is not None:
        detail["after"] = after_value
    if trace_id:
        detail["trace_id"] = trace_id

    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail if detail else None,
        ip_address=ip_address,
    )
    db.add(log_entry)


def audit_action(
    resource_type: str | None = None,
    action: str | None = None,
    extract_resource_id: Callable | None = None,
):
    """Decorator that logs an audit entry after the wrapped endpoint executes.

    Usage::

        @router.post("/items")
        @audit_action(resource_type="item", action="create")
        async def create_item(...):
            ...
    """

    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any):
            result = await fn(*args, **kwargs)

            # Try to extract audit context from kwargs / request
            db: AsyncSession | None = kwargs.get("db")
            request: Request | None = kwargs.get("request")
            user_jwt = kwargs.get("_user") or kwargs.get("user")

            if db is None:
                return result

            user_id = None
            if user_jwt:
                try:
                    user_id = int(getattr(user_jwt, "sub", None) or 0)
                except (ValueError, TypeError):
                    pass

            resource_id = None
            if extract_resource_id:
                try:
                    resource_id = extract_resource_id(kwargs, result)
                except Exception:
                    pass

            trace_id = None
            ip_address = None
            if request:
                trace_id = getattr(request.state, "trace_id", None)
                ip_address = request.client.host if request.client else None

            act = action or fn.__name__
            rt = resource_type

            try:
                await log_audit(
                    db=db,
                    user_id=user_id,
                    action=act,
                    resource_type=rt,
                    resource_id=resource_id,
                    ip_address=ip_address,
                    trace_id=trace_id,
                )
            except Exception:
                # Audit logging should never break the main operation
                pass

            return result

        return wrapper

    return decorator
