"""Tests for JWT auth, RBAC guards, and security helpers."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    TokenPayload,
    require_role,
    require_permission,
)
from app.config import settings
from app.core.exceptions import AuthenticationError, ForbiddenError


class TestPasswordHelpers:
    """Test password hashing and verification."""

    def test_hash_and_verify(self):
        hashed = hash_password("my_secret_password")
        assert verify_password("my_secret_password", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct_password")
        assert not verify_password("wrong_password", hashed)

    def test_different_hashes(self):
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        # bcrypt uses random salt, so hashes should differ
        assert h1 != h2
        # But both should verify
        assert verify_password("same_password", h1)
        assert verify_password("same_password", h2)


class TestJWT:
    """Test JWT token creation and decoding."""

    def test_create_and_decode(self):
        token = create_access_token(subject="user_123")
        payload = decode_access_token(token)
        assert payload["sub"] == "user_123"

    def test_extra_claims(self):
        token = create_access_token(subject="user_123", extra={"role": "admin", "tenant": "acme"})
        payload = decode_access_token(token)
        assert payload["role"] == "admin"
        assert payload["tenant"] == "acme"

    def test_token_has_expiry(self):
        token = create_access_token(subject="user_123")
        payload = decode_access_token(token)
        assert "exp" in payload
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp > datetime.now(timezone.utc)

    def test_invalid_token_raises(self):
        with pytest.raises(AuthenticationError):
            decode_access_token("not-a-valid-token")

    def test_expired_token_raises(self):
        # Create a token that expired 1 second ago using python-jose
        from jose import jwt as pyjwt
        expired_payload = {
            "sub": "user_123",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        }
        expired_token = pyjwt.encode(expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        with pytest.raises(AuthenticationError):
            decode_access_token(expired_token)


class TestTokenPayload:
    """Test TokenPayload schema validation."""

    def test_valid_payload(self):
        payload = TokenPayload(sub="user_1", role="admin")
        assert payload.sub == "user_1"
        assert payload.role == "admin"

    def test_default_role(self):
        payload = TokenPayload(sub="user_1")
        assert payload.role == "viewer"


class TestRBAC:
    """Test role and permission guards."""

    def test_require_role_allows_admin(self):
        dep = require_role("admin")
        user = TokenPayload(sub="1", role="admin")
        result = dep(user)
        assert result.role == "admin"

    def test_require_role_rejects_viewer(self):
        dep = require_role("admin")
        user = TokenPayload(sub="1", role="viewer")
        with pytest.raises(ForbiddenError):
            dep(user)

    def test_require_role_multiple_allowed(self):
        dep = require_role("admin", "analyst")
        user = TokenPayload(sub="1", role="analyst")
        result = dep(user)
        assert result.role == "analyst"

    def test_require_permission_dashboard_allows_viewer(self):
        dep = require_permission("dashboard:*")
        user = TokenPayload(sub="1", role="viewer")
        result = dep(user)
        assert result.role == "viewer"

    def test_require_permission_data_rejects_viewer(self):
        dep = require_permission("data:*")
        user = TokenPayload(sub="1", role="viewer")
        with pytest.raises(ForbiddenError):
            dep(user)

    def test_require_permission_admin_only(self):
        dep = require_permission("user:*")
        user = TokenPayload(sub="1", role="analyst")
        with pytest.raises(ForbiddenError):
            dep(user)

    def test_require_permission_unknown_defaults_to_admin(self):
        dep = require_permission("unknown:action")
        user = TokenPayload(sub="1", role="viewer")
        with pytest.raises(ForbiddenError):
            dep(user)

        # But admin should pass
        user_admin = TokenPayload(sub="1", role="admin")
        result = dep(user_admin)
        assert result.role == "admin"
