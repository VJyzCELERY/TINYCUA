"""Shared pytest fixtures for unit tests."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def mock_config_getter():
    """Create a mock config."""
    config = MagicMock()
    config.auth.jwt_secret = "test-secret-key"
    config.auth.jwt_algorithm = "HS256"
    config.auth.jwt_expiration_hours = 24
    config.auth.api_key = None
    config.database.url = "sqlite:///:memory:"
    config.server.host = "0.0.0.0"
    config.server.port = 8000
    return config


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock critical dependencies at the start of each test."""
    mock_cfg = mock_config_getter()
    with patch("tinycua_backend.config.get_config", return_value=mock_cfg):
        with patch("tinycua_backend.auth.core.get_config", return_value=mock_cfg):
            with patch("tinycua_backend.storage.database.get_engine") as mock_engine:
                mock_eng = MagicMock()
                mock_engine.return_value = mock_eng
                with patch("tinycua_backend.storage.database.get_session_local") as mock_session_local:
                    mock_session = MagicMock()
                    mock_session_local.return_value = mock_session
                    with patch("tinycua_backend.storage.database.create_tables"):
                        yield {
                            "config": mock_cfg,
                            "engine": mock_eng,
                            "session": mock_session,
                        }


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.add.return_value = None
    db.commit.return_value = None
    db.flush.return_value = None
    db.refresh.return_value = None
    return db


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return mock_config_getter()


@pytest.fixture
def test_tenant():
    """Create a test tenant."""
    from tinycua_backend.tenant.models import TenantType
    tenant = MagicMock()
    tenant.id = "tenant-123"
    tenant.name = "Test Tenant"
    tenant.tenant_type = TenantType.STANDARD
    return tenant


@pytest.fixture
def test_user():
    """Create a test user."""
    user = MagicMock()
    user.id = "user-123"
    user.email = "test@example.com"
    user.password_hash = "hashed_password"
    user.tenant_id = "tenant-123"
    return user


@pytest.fixture
def auth_token(test_tenant, test_user):
    """Create a valid JWT token for testing."""
    from tinycua_backend.auth.core import create_jwt_token
    from datetime import timedelta

    token = create_jwt_token(
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        expires_delta=timedelta(hours=1),
    )
    return token


@pytest.fixture
def mock_session_store():
    """Create a mock SessionStore."""
    store = MagicMock()
    mock_session = MagicMock()
    mock_session.id = "session-123"
    mock_session.name = "Test Session"
    mock_session.created_at = datetime.now(timezone.utc)
    mock_session.updated_at = datetime.now(timezone.utc)

    store.create_session.return_value = mock_session
    store.list_sessions.return_value = [mock_session]
    store.get_session.return_value = mock_session
    store.get_messages.return_value = []

    mock_message = MagicMock()
    mock_message.id = "message-123"
    mock_message.role = "user"
    mock_message.content = "Hello"
    mock_message.turn_index = 0
    mock_message.created_at = datetime.now(timezone.utc)
    store.add_message.return_value = mock_message

    return store
