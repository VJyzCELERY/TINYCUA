"""Integration tests for API endpoints using TestClient."""

import os
import secrets
import tempfile

import pytest

TEST_PASSWORD = "TestPassword123!"
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Override the global mock_dependencies fixture for integration tests."""
    yield


@pytest.fixture(autouse=True)
def clear_rate_limit_store():
    """Clear the in-memory rate limit store before each test."""
    from tinycua_backend.api.auth import _rate_limit_store
    _rate_limit_store.clear()
    yield


@pytest.fixture
def client():
    """Create a TestClient with SQLite database."""
    db_file = tempfile.mktemp(suffix=".db")
    database_url = f"sqlite:///{db_file}"
    os.environ["JWT_SECRET"] = "test-secret-for-integration-tests"

    from sqlalchemy import create_engine

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )

    from tinycua_sdk.storage.store import SessionStore
    SessionStore(database_url).create_tables()

    from tinycua_backend.storage import database as db_module
    from tinycua_backend import config as config_module

    original_engine = db_module._engine
    original_session_local = db_module._SessionLocal
    original_config = config_module._config
    original_config_load = config_module.Config.load

    db_module._engine = engine
    db_module._SessionLocal = None

    test_config = config_module.Config()
    test_config.database.url = database_url
    test_config.auth.jwt_secret = "test-secret-for-integration-tests"
    config_module._config = test_config
    config_module.Config.load = lambda *args, **kwargs: test_config

    from tinycua_backend.main import app

    with TestClient(app) as test_client:
        yield test_client

    db_module._engine = original_engine
    db_module._SessionLocal = original_session_local
    config_module._config = original_config
    config_module.Config.load = original_config_load

    os.unlink(db_file)


@pytest.fixture
def auth_headers(client):
    """Get authentication headers for testing."""
    response = client.post(
        "/v1/auth/register",
        json={
            "email": "integration@test.com",
            "password": TEST_PASSWORD,
        },
    )
    data = response.json()
    token = data["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_register_user(self, client):
        """Test user registration."""
        response = client.post(
            "/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": TEST_PASSWORD,
                "tenant_name": "Test Tenant",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["tenant_id"] is not None
        assert data["user_id"] is not None
        assert "api_key" in data

    def test_register_invalid_email(self, client):
        """Test registration with invalid email fails."""
        response = client.post(
            "/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": TEST_PASSWORD,
            },
        )
        assert response.status_code == 422

    def test_register_short_password(self, client):
        """Test registration with short password fails."""
        response = client.post(
            "/v1/auth/register",
            json={
                "email": "test2@example.com",
                "password": "short",
            },
        )
        assert response.status_code == 422

    def test_login_user(self, client):
        """Test user login."""
        # First register
        register_response = client.post(
            "/v1/auth/register",
            json={
                "email": "login@test.com",
                "password": TEST_PASSWORD,
            },
        )
        tenant_id = register_response.json()["tenant_id"]

        # Then login
        response = client.post(
            "/v1/auth/login",
            json={
                "email": "login@test.com",
                "password": TEST_PASSWORD,
                "tenant_id": tenant_id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent user returns 401."""
        response = client.post(
            "/v1/auth/login",
            json={
                "email": "nonexistent@test.com",
                "password": TEST_PASSWORD,
            },
        )
        assert response.status_code == 401

    def test_login_success_single_tenant(self, client):
        """Test login succeeds with email and password for single tenant user."""
        register_response = client.post(
            "/v1/auth/register",
            json={
                "email": "user-login@test.com",
                "password": TEST_PASSWORD,
            },
        )
        assert register_response.status_code == 201

        response = client.post(
            "/v1/auth/login",
            json={
                "email": "user-login@test.com",
                "password": TEST_PASSWORD,
            },
        )
        assert response.status_code == 200
        assert "access_token" in response.json()


class TestSessionEndpoints:
    """Tests for session endpoints."""

    def test_create_session(self, client, auth_headers):
        """Test creating a session."""
        response = client.post(
            "/v1/sessions",
            json={"agent_id": "agent-123", "name": "Test Session"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Session"
        assert "id" in data

    def test_list_sessions(self, client, auth_headers):
        """Test listing sessions."""
        client.post(
            "/v1/sessions",
            json={"agent_id": "agent-123", "name": "Test Session"},
            headers=auth_headers,
        )

        response = client.get("/v1/sessions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_session(self, client, auth_headers):
        """Test getting a session by ID."""
        create_response = client.post(
            "/v1/sessions",
            json={"agent_id": "agent-123", "name": "Test Session"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        response = client.get(f"/v1/sessions/{session_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id

    def test_create_message(self, client, auth_headers):
        """Test creating a message in a session."""
        # Create session
        create_response = client.post(
            "/v1/sessions",
            json={"agent_id": "agent-123", "name": "Test Session"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # Create message
        response = client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"role": "user", "content": "Hello"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "user"
        assert data["content"] == "Hello"

    def test_list_messages(self, client, auth_headers):
        """Test listing messages in a session."""
        # Create session and message
        create_response = client.post(
            "/v1/sessions",
            json={"agent_id": "agent-123", "name": "Test Session"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"role": "user", "content": "Hello"},
            headers=auth_headers,
        )

        response = client.get(
            f"/v1/sessions/{session_id}/messages",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
