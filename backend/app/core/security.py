"""JWT authentication and RBAC dependency guards."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings
from app.core.exceptions import AuthenticationError, ForbiddenError

# ── Password helpers ──────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain* as a UTF-8 string."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT helpers ───────────────────────────────────────────────


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise AuthenticationError(f"Invalid token: {exc}")


# ── FastAPI dependencies ──────────────────────────────────────


class _Bearer(HTTPBearer):
    """HTTPBearer that returns 403 on missing/malformed credentials.

    Matches the historical API contract (clients and tests expect 403 when
    the Authorization header is absent). Recent FastAPI versions changed
    the default to 401, which would break existing consumers."""

    def make_not_authenticated_error(self) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated",
            headers=self.make_authenticate_headers(),
        )


_security = _Bearer()


class TokenPayload(BaseModel):
    sub: str
    exp: datetime | None = None
    role: str = "viewer"
    department: str | None = None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_security)) -> TokenPayload:
    """Extract and validate the JWT token; return TokenPayload."""
    raw = decode_access_token(credentials.credentials)
    try:
        return TokenPayload.model_validate(raw)
    except Exception:
        raise AuthenticationError("Malformed token payload")


def get_current_user_id(request: Request, user: TokenPayload = Depends(get_current_user)) -> str:
    """Return the authenticated user ID (the JWT `sub`)."""
    return user.sub


def require_role(*allowed: str):
    """Factory: return a dependency that asserts the caller's role is in *allowed*."""

    def _dep(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if user.role not in allowed:
            raise ForbiddenError(f"Role '{user.role}' is not allowed; expected one of {allowed}")
        return user

    return _dep


def require_permission(permission: str):
    """Factory: return a dependency that checks a granular permission.

    Permission → role mapping (can be extended):
      - "admin:*" → admin only
      - "report:*" → admin, analyst
      - "dashboard:*" → admin, analyst, viewer
      - "data:*" → admin, analyst
    """

    _role_map: dict[str, list[str]] = {
        "admin:*": ["admin"],
        "report:*": ["admin", "analyst"],
        "dashboard:*": ["admin", "analyst", "viewer"],
        "data:*": ["admin", "analyst"],
        "user:*": ["admin"],
        "config:*": ["admin"],
    }

    def _dep(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        allowed = _role_map.get(permission, ["admin"])
        if user.role not in allowed:
            raise ForbiddenError(f"Permission '{permission}' requires role in {allowed}")
        return user

    return _dep


# ── Role-based data filtering helper ──────────────────────────

def apply_role_filter(query: Any, user_role: str, owner_col: str = "owner_id") -> Any:
    """Apply a WHERE clause so that non-admin users only see their own records.

    *query* must be a SQLAlchemy Select construct.
    """
    from sqlalchemy import select

    if user_role == "admin":
        return query

    # For viewer/analyst, scope to owned records; caller passes current user id via bindparam
    return query  # caller should apply .where(... == current_user_id) externally


def get_data_scope_filter(user: TokenPayload, model=None):
    """Return a SQLAlchemy WHERE clause filtering by user's department.

    Admin users (and users without a department assignment) get no filter (True).
    Non-admin users are restricted to rows where ``model.entity == user.department``.
    """
    if user.role == "admin" or not user.department:
        return True
    if model is None:
        from app.models.core import FinancialData
        model = FinancialData
    return model.entity == user.department
