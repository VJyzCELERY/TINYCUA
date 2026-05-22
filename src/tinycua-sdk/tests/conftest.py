"""Conftest for integration tests."""

import os
from pathlib import Path

import pytest
import asyncio
import logging

from dotenv import load_dotenv


class FakeLLMResponse:
    """Fake httpx response for LLM client unit tests.

    Provides a consistent interface across tests without defining
    separate FakeResponse classes in each test method.
    """

    def __init__(self, json_data=None, status_code=200):
        self.status_code = status_code
        self._json_data = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                f"{self.status_code} error", request=None, response=self
            )

    def json(self):
        return self._json_data


# =============================================================================
# Configuration
# =============================================================================

# Load subproject root .env first (local LLM server credentials, gitignored)
env_root = Path(__file__).parents[1] / ".env"
if env_root.exists():
    load_dotenv(env_root)

# Load environment from .env.test (user-specific, gitignored)
# Checks root-level then tests/-level; falls back to .env.test.example (committed template)
env_test = Path(__file__).parents[1] / ".env.test"
if env_test.exists():
    load_dotenv(env_test)
else:
    env_test = Path(__file__).parent / ".env.test"
    if env_test.exists():
        load_dotenv(env_test)
    else:
        env_test_example = Path(__file__).parents[1] / ".env.test.example"
        if env_test_example.exists():
            load_dotenv(env_test_example)
        else:
            env_test_example = Path(__file__).parent / ".env.test.example"
            if env_test_example.exists():
                load_dotenv(env_test_example)

# Set environment variables for tests with defaults
os.environ.setdefault("LLM_BASE_URL", "http://localhost:1234/v1")
os.environ.setdefault("LLM_MODEL", "qwen/qwen3.5-9b")
os.environ.setdefault("LLM_API_KEY", "dummy")

# Backward compatibility: map LLM_* vars to TINYCUA_* names
os.environ.setdefault("TINYCUA_PROVIDER", "openai-chat-completions")
os.environ.setdefault("TINYCUA_MODEL", os.environ["LLM_MODEL"])
os.environ.setdefault("TINYCUA_BASE_URL", os.environ["LLM_BASE_URL"])


# =============================================================================
# Logging Configuration
# =============================================================================


def pytest_configure(config):
    """Configure logging for tests."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_timeout():
    """Default timeout for async operations."""
    return 30


# =============================================================================
# Markers
# =============================================================================

# Custom markers are defined in pyproject.toml
