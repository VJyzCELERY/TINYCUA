"""Conftest for integration tests."""

import pytest
import asyncio
import os
import logging


# =============================================================================
# Configuration
# =============================================================================

# Set environment variables for tests
os.environ["TINYCUA_PROVIDER"] = "lmstudio"
os.environ["TINYCUA_MODEL"] = "qwen/qwen3.5-9b"
os.environ["TINYCUA_BASE_URL"] = "http://localhost:1234"
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

# Define custom markers
pytestmark = pytest.mark.asyncio
