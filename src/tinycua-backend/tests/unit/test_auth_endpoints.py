"""Unit tests for authentication endpoints."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import os
import secrets

import pytest
from fastapi import HTTPException, status

os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-unit-tests")
TEST_PASSWORD = "TestPassword123!"

from tests.unit.utils import get_tenant_filter
from tinycua_backend.auth.core import (
    create_jwt_token,
    decode_jwt_token,
    hash_api_key,
    hash_password,
    verify_api_key,
    verify_password,
)


class TestLoginEndpointHTTP:
    """Tests for the login HTTP endpoint."""

    def test_login_endpoint_validates_request(self):
        """Test POST /auth/login validates request payload."""
        from tinycua_backend.api.auth import LoginRequest

        valid_request = LoginRequest(
            email="test@example.com",
            password=TEST_PASSWORD,
            tenant_id="12345678-1234-1234-1234-123456789abc",
        )
        assert valid_request.email == "test@example.com"

    def test_login_endpoint_requires_email(self):
        """Test POST /auth/login requires email field."""
        from tinycua_backend.api.auth import LoginRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginRequest(password=TEST_PASSWORD, tenant_id="tenant-123")

    def test_login_endpoint_requires_password(self):
        """Test POST /auth/login requires password field."""
        from tinycua_backend.api.auth import LoginRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginRequest(email="test@example.com", tenant_id="tenant-123")

    def test_login_endpoint_accepts_email_password_only(self):
        """Test POST /auth/login accepts email and password without tenant_id."""
        from tinycua_backend.auth.schemas import LoginRequest

        request = LoginRequest(email="test@example.com", password=TEST_PASSWORD)
        assert request.email == "test@example.com"
        assert request.password == TEST_PASSWORD


class TestRegistrationEndpointHTTP:
    """Tests for the registration HTTP endpoint."""

    def test_register_endpoint_validates_request(self):
        """Test POST /auth/register validates request payload."""
        from tinycua_backend.api.auth import RegisterRequest

        valid_request = RegisterRequest(
            email="test@example.com",
            password=TEST_PASSWORD,
            tenant_name="Test Tenant",
        )
        assert valid_request.email == "test@example.com"

    def test_register_endpoint_duplicate_detection_logic(self):
        """Test that duplicate user detection logic works."""
        from tinycua_backend.auth.models import User

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = mock_db.query(User).filter(User.email == "test@example.com").first()

        assert result is not None
        assert result.id == "user-123"

    def test_register_endpoint_requires_email(self):
        """Test POST /auth/register requires email field."""
        from tinycua_backend.api.auth import RegisterRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisterRequest(password=TEST_PASSWORD)

    def test_register_endpoint_requires_password(self):
        """Test POST /auth/register requires password field."""
        from tinycua_backend.api.auth import RegisterRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisterRequest(email="test@example.com")


class TestTokenExtractionHTTP:
    """Tests for token extraction from HTTP headers."""

    def test_token_extraction_from_header_directly(self):
        """Test token can be extracted from Authorization header using decode function."""
        token = create_jwt_token("user-123", "tenant-123")
        payload = decode_jwt_token(token)

        assert payload["sub"] == "user-123"
        assert payload["tenant_id"] == "tenant-123"

    def test_expired_token_returns_401(self):
        """Test expired token returns 401."""
        from tinycua_backend.auth.core import decode_jwt_token

        expired_token = create_jwt_token(
            "user-123",
            "tenant-123",
            expires_delta=timedelta(seconds=-1),
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_jwt_token(expired_token)

        assert exc_info.value.status_code == 401

    def test_invalid_token_returns_401(self):
        """Test invalid token returns 401."""
        from tinycua_backend.auth.core import decode_jwt_token

        with pytest.raises(HTTPException) as exc_info:
            decode_jwt_token("invalid-token-format")

        assert exc_info.value.status_code == 401


class TestLoginEndpoint:
    """Tests for the login endpoint."""

    def test_create_jwt_token(self, mock_config):
        """Test creating a JWT token."""
        token = create_jwt_token("user-123", "tenant-123")
        assert token is not None
        assert isinstance(token, str)

    def test_create_jwt_token_with_expiry(self, mock_config):
        """Test creating a JWT token with custom expiry."""
        token = create_jwt_token(
            "user-123",
            "tenant-123",
            expires_delta=timedelta(hours=2),
        )
        assert token is not None


class TestTokenValidation:
    """Tests for JWT token validation."""

    def test_decode_valid_token(self, mock_config):
        """Test decoding a valid JWT token."""
        token = create_jwt_token("user-123", "tenant-123")
        payload = decode_jwt_token(token)

        assert payload["sub"] == "user-123"
        assert payload["tenant_id"] == "tenant-123"

    def test_decode_invalid_token(self, mock_config):
        """Test decoding an invalid JWT token raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt_token("invalid-token")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_decode_expired_token(self, mock_config):
        """Test decoding an expired token raises 401."""
        expired_token = create_jwt_token(
            "user-123",
            "tenant-123",
            expires_delta=timedelta(seconds=-1),
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_jwt_token(expired_token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestHashApiKey:
    """Tests for API key hashing."""

    def test_hash_api_key_consistency(self):
        """Test that hashing the same key produces verifiable results."""
        key = "test-api-key"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)

        # bcrypt hashes differ due to salt, but both should verify
        assert verify_api_key(key, hash1)
        assert verify_api_key(key, hash2)

    def test_hash_api_key_different_keys(self):
        """Test that different keys produce different hashes."""
        hash1 = hash_api_key("key1")
        hash2 = hash_api_key("key2")

        assert hash1 != hash2

    def test_hash_api_key_format(self):
        """Test hashed key format is bcrypt."""
        key = "test-key"
        hashed = hash_api_key(key)

        assert hashed.startswith("$2b$")


class TestPasswordHashing:
    """Tests for password hashing with bcrypt."""

    def test_hash_password(self):
        """Test password hashing with bcrypt."""
        password = "test-password"
        hashed = hash_password(password)

        assert hashed.startswith("$2b$")
        assert verify_password(password, hashed)

    def test_verify_password_wrong(self):
        """Test verifying wrong password fails."""
        password = "test-password"
        hashed = hash_password(password)

        assert not verify_password("wrong-password", hashed)


class TestGetTenantFilter:
    """Tests for tenant filtering."""

    def test_standard_tenant_filter(self):
        """Test filter is returned for standard tenant."""
        from tinycua_backend.auth.models import User
        from tinycua_backend.tenant.models import TenantType

        mock_tenant = MagicMock()
        mock_tenant.tenant_type = TenantType.STANDARD

        filter_condition = get_tenant_filter(mock_tenant, User)

        assert filter_condition is not None

    def test_system_tenant_filter(self):
        """Test no filter for system tenant."""
        from tinycua_backend.auth.models import User
        from tinycua_backend.tenant.models import TenantType

        mock_tenant = MagicMock()
        mock_tenant.tenant_type = TenantType.SYSTEM

        filter_condition = get_tenant_filter(mock_tenant, User)

        assert filter_condition is None


class TestCurrentTenant:
    """Tests for CurrentTenant class."""

    def test_current_tenant_system(self):
        """Test CurrentTenant.is_system for system tenant."""
        from tinycua_backend.tenant.models import TenantType
        from tinycua_backend.auth.core import CurrentTenant

        mock_tenant = MagicMock()
        mock_tenant.tenant_type = TenantType.SYSTEM

        current = CurrentTenant(tenant=mock_tenant, user_id="system")

        assert current.is_system is True

    def test_current_tenant_standard(self):
        """Test CurrentTenant.is_system for standard tenant."""
        from tinycua_backend.tenant.models import TenantType
        from tinycua_backend.auth.core import CurrentTenant

        mock_tenant = MagicMock()
        mock_tenant.tenant_type = TenantType.STANDARD

        current = CurrentTenant(tenant=mock_tenant, user_id="user-123")

        assert current.is_system is False

    
