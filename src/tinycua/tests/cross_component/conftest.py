"""Shared cross-component test fixtures for TinyCUA."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class MockBackend:
    """Mock Backend server for testing."""

    def __init__(self):
        self.connected = False
        self.authenticated = False
        self.sessions = {}
        self.agents = {}
        self.messages = {}

    async def connect(self):
        self.connected = True
        return {"status": "connected"}

    async def authenticate(self, api_key):
        self.authenticated = True
        return {"access_token": api_key, "tenant_id": "tenant-123", "user_id": "user-123"}

    async def health_check(self):
        return self.connected


@pytest.fixture
def mock_backend():
    """Create a mock Backend server for testing.

    Returns:
        MockBackend instance for testing.
    """
    return MockBackend()


@pytest.fixture
def sdk_client(mock_backend):
    """Create an SDK client connected to mock Backend.

    Args:
        mock_backend: Mock backend fixture.

    Returns:
        BackendClient instance connected to mock backend.
    """
    from unittest.mock import AsyncMock
    from tinycua.clients import BackendClient

    client = BackendClient(
        base_url="http://localhost:8000",
        api_key="test-api-key",
    )
    client._mock_backend = mock_backend
    client._client = AsyncMock()
    return client


@pytest.fixture
def device_a(mock_backend):
    """Create Device A instance for multi-device testing.

    Args:
        mock_backend: Mock backend fixture.

    Returns:
        Dict representing Device A.
    """
    return {"id": "device-a", "name": "Device A", "sessions": {}}


@pytest.fixture
def device_b(mock_backend):
    """Create Device B instance for multi-device testing.

    Args:
        mock_backend: Mock backend fixture.

    Returns:
        Dict representing Device B.
    """
    return {"id": "device-b", "name": "Device B", "sessions": {}}


@pytest.fixture
def sample_session():
    """Create a sample session for testing.

    Returns:
        Dict representing a session.
    """
    return {
        "id": "session-123",
        "agent_id": "agent-abc",
        "name": "test-session",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_agent():
    """Create a sample agent for testing.

    Returns:
        Dict representing an agent.
    """
    return {
        "agent_id": "agent-abc",
        "name": "test-agent",
        "config": {"model": "gpt-4"},
    }
