"""Conftest for integration tests."""

import pytest
import asyncio
import os
import logging


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

# Set environment variables for tests
os.environ["TINYCUA_PROVIDER"] = "openai-compatible"
os.environ["TINYCUA_MODEL"] = "qwen/qwen3.5-9b"
os.environ["TINYCUA_BASE_URL"] = "http://localhost:1234/v1"
os.environ["TINYCUA_API_KEY"] = "dummy"


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
