"""Conftest for integration tests."""

import os
import pytest


def pytest_configure(config):
    """Configure integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as requiring local LLM server"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add skip logic for local LLM unavailable."""
    llm_url = os.environ.get("TINYCUA_TEST_LM_STUDIO_URL")

    if not llm_url:
        skip_llm = pytest.mark.skip(
            reason="Local LLM not available. Set TINYCUA_TEST_LM_STUDIO_URL to run."
        )
        for item in items:
            if "test_local_run" in item.fspath.basename:
                if "integration" in item.keywords:
                    item.add_marker(skip_llm)