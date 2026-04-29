"""Conftest for integration tests."""

import pytest
from unittest.mock import AsyncMock, patch


def pytest_configure(config):
    """Configure integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as requiring local LLM server"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add skip logic for local LLM unavailable."""
    pass


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for integration tests."""
    with patch("tinycua_sdk.agent.executor.LLMClient") as mock:
        mock.return_value.chat = AsyncMock(return_value="Mocked response")
        yield mock


@pytest.fixture
def mock_llm_with_tool_calls():
    """Mock LLM client that returns tool calls then a final response."""
    with patch("tinycua_sdk.agent.executor.LLMClient") as mock:
        mock.return_value.chat = AsyncMock(
            side_effect=[
                '{"tool_calls": [{"name": "search", "arguments": {"query": "quantum"}}]}',
                "Quantum computing is...",
            ]
        )
        yield mock
