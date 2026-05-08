"""Conftest for integration tests."""

import os

import httpx
import pytest


def pytest_configure(config):
    """Configure integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as requiring local LLM server"
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when LLM server is unreachable."""
    base_url = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1")
    try:
        httpx.get(f"{base_url}/models", timeout=5).raise_for_status()
        reachable = True
    except Exception:
        reachable = False

    if not reachable:
        skip_mark = pytest.mark.skip(reason="LLM server not reachable")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_mark)
