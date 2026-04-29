"""Conftest for unit tests."""

import pytest
import os
import tempfile
from unittest.mock import MagicMock

os.environ["TINYCUA_PROVIDER"] = "openai-compatible"
os.environ["TINYCUA_MODEL"] = "qwen/qwen3.5-9b"
os.environ["TINYCUA_BASE_URL"] = "http://localhost:1234/v1"
os.environ["TINYCUA_API_KEY"] = "dummy"


@pytest.fixture
def mock_provider():
    """Mock LLM provider."""
    provider = MagicMock()
    provider.complete = MagicMock(return_value="test response")
    provider.complete_async = MagicMock(return_value="test response")
    return provider


@pytest.fixture
def mock_agent_config():
    """Mock agent configuration."""
    return {
        "name": "test-agent",
        "model": "qwen/qwen3.5-9b",
        "provider": "openai-compatible",
        "temperature": 0.7,
        "max_tokens": 2048,
    }


@pytest.fixture
def temp_skill_dir(tmp_path):
    """Temporary skills directory."""
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text("name: test_skill\nversion: 1.0.0")
    return skill_dir


@pytest.fixture
def mock_llm_response():
    """Mock LLM response."""
    return {"choices": [{"message": {"content": "Test response"}}]}


@pytest.fixture
def mock_messages():
    """Mock message list."""
    return [{"role": "user", "content": "Hello"}]


@pytest.fixture
def mock_tool():
    """Mock tool definition."""
    return {
        "name": "test_tool",
        "description": "A test tool",
        "parameters": {
            "type": "object",
            "properties": {"arg": {"type": "string"}},
            "required": ["arg"],
        },
    }
