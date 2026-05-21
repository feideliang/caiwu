"""Auth endpoints: login, me, user management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AuthenticationError, ResourceNotFoundError
from app.core.response import APIResponse, ErrorCode
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from app.db.session import get_db
from app.models.v4 import Role, User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=APIResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> APIResponse:
    """Authenticate and return a JWT access token."""
    stmt = select(User).where(User.username == body.username).options(selectinload(User.role))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise AuthenticationError("Invalid username or password")

    if not user.is_active:
        raise AuthenticationError("Account is disabled")

    user.last_login_at = datetime.now()
    await db.flush()

    token = create_access_token(
        subject=str(user.id),
        extra={"role": user.role.name if user.role else "viewer", "department": user.department},
    )
    return APIResponse.success(data={
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.name if user.role else "viewer",
            "department": user.department,
            "is_active": user.is_active,
        },
    })


@router.get("/me", response_model=APIResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    user_jwt = Depends(get_current_user),
) -> APIResponse:
    """Return the current authenticated user's profile."""
    user_id = int(user_jwt.sub)
    stmt = select(User).where(User.id == user_id).options(selectinload(User.role))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise ResourceNotFoundError("User not found")

    data = UserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        role_name=user.role.name if user.role else "viewer",
        department=user.department,
        is_active=user.is_active,
    )
    return APIResponse.success(data=data.model_dump())


@router.post("/change-password", response_model=APIResponse)
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    user_jwt = Depends(get_current_user),
) -> APIResponse:
    user_id = int(user_jwt.sub)
    user = await db.get(User, user_id)
    if user is None:
        raise ResourceNotFoundError("User not found")
    if not verify_password(body.old_password, user.password_hash):
        raise AuthenticationError("Old password is incorrect")
    user.password_hash = hash_password(body.new_password)
    await db.flush()
    return APIResponse.success(message="Password updated")


# ── Admin: user CRUD ──────────────────────────────────────────

admin_router = APIRouter(prefix="/users", tags=["users"])


@admin_router.post("", response_model=APIResponse)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_role("admin")),
) -> APIResponse:
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        return APIResponse.error(code=ErrorCode.ALREADY_EXISTS, message="Username already exists")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        role_id=body.role_id,
        department=body.department,
    )
    db.add(user)
    await db.flush()
    return APIResponse.success(data={"id": user.id})


@admin_router.get("", response_model=APIResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_role("admin")),
) -> APIResponse:
    stmt = select(User).options(selectinload(User.role)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    users = result.scalars().all()

    count_stmt = select(func.count()).select_from(User)
    total = (await db.execute(count_stmt)).scalar_one()

    items = [
        UserRead(
            id=u.id,
            username=u.username,
            email=u.email,
            role_name=u.role.name if u.role else "viewer",
            department=u.department,
            is_active=u.is_active,
        ).model_dump()
        for u in users
    ]
    return APIResponse.success(data={"items": items, "total": total, "page": page, "page_size": page_size})


@admin_router.put("/{user_id}", response_model=APIResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_role("admin")),
) -> APIResponse:
    user = await db.get(User, user_id)
    if user is None:
        raise ResourceNotFoundError("User not found")
    update_data = body.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(user, k, v)
    await db.flush()
    return APIResponse.success(message="User updated")


@admin_router.delete("/{user_id}", response_model=APIResponse)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_role("admin")),
) -> APIResponse:
    user = await db.get(User, user_id)
    if user is None:
        raise ResourceNotFoundError("User not found")
    await db.delete(user)
    await db.flush()
    return APIResponse.success(message="User deleted")
