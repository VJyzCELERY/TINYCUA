"""Shared fixtures for TUI component unit tests."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_terminal():
    """Mock terminal input/output for TUI tests."""
    return MagicMock()


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "model": "qwen/qwen3.5-9b",
        "api_base": "http://localhost:1234",
        "api_key": "test-key",
        "temperature": 0.7,
        "max_tokens": 2048,
    }


@pytest.fixture
def sample_session():
    """Sample session for testing."""
    return {
        "id": "test-session-001",
        "name": "Test Session",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
        "created_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def mock_agent():
    """Mock agent for testing."""
    return MagicMock(name="test-agent")


@pytest.fixture
def empty_session_list():
    """Empty session list for testing."""
    return []


@pytest.fixture
def sample_backend_response():
    """Sample backend response for testing."""
    return {"agent_id": "test-001"}
