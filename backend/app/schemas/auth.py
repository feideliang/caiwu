"""Auth-related Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: int
    username: str
    email: str | None
    role_name: str
    department: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: str | None = None
    password: str = Field(min_length=6, max_length=128)
    role_id: int = 3  # default viewer
    department: str | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    is_active: bool | None = None
    role_id: int | None = None
    department: str | None = None


class RoleRead(BaseModel):
    id: int
    name: str
    display_name: str
    permissions: list[str] | None
    description: str | None

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    permissions: list[str] | None = None
    description: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)
