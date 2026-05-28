"""Pytest configuration and fixtures."""

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "lm_studio: requires LM Studio running")
    config.addinivalue_line("markers", "backend: requires backend server running")
    config.addinivalue_line(
        "markers", "remote_runner: requires remote runner server running"
    )


@pytest.fixture(scope="session")
def lm_studio_url():
    """Get LM Studio URL from environment or default."""
    import os

    return os.environ.get("TINYCUA_LM_STUDIO_URL", "http://localhost:1234")


@pytest.fixture(scope="session")
def backend_url():
    """Get backend URL from environment or default."""
    import os

    return os.environ.get("TINYCUA_BACKEND_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def remote_runner_url():
    """Get remote runner URL from environment or default."""
    import os

    return os.environ.get("TINYCUA_RUNNER_URL", "http://localhost:8001")


async def check_service(url: str, timeout: float = 2.0) -> bool:
    """Check if a service is available."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{url}/health")
            return response.status_code == 200
    except Exception:
        return False


@pytest.fixture
async def lm_studio_available(lm_studio_url):
    """Check if LM Studio is available."""
    return await check_service(lm_studio_url)


@pytest.fixture
async def backend_available(backend_url):
    """Check if backend is available."""
    return await check_service(backend_url)


@pytest.fixture
async def remote_runner_available(remote_runner_url):
    """Check if remote runner is available."""
    return await check_service(remote_runner_url)


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests when services are not available."""
    skip_lm_studio = pytest.mark.skip(reason="LM Studio not available")
    skip_backend = pytest.mark.skip(reason="Backend server not available")
    skip_runner = pytest.mark.skip(reason="Remote runner not available")

    for item in items:
        if "lm_studio" in item.keywords:
            item.add_marker(skip_lm_studio)
        if "backend" in item.keywords:
            item.add_marker(skip_backend)
        if "remote_runner" in item.keywords:
            item.add_marker(skip_runner)
