"""Conftest for integration tests."""

import os
import pytest


def pytest_configure(config):
    """Configure integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as requiring LM Studio"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add skip logic for LM Studio unavailable."""
    lm_studio_url = os.environ.get("TINYCUA_TEST_LM_STUDIO_URL")

    if not lm_studio_url:
        skip_lmstudio = pytest.mark.skip(
            reason="LM Studio not available. Set TINYCUA_TEST_LM_STUDIO_URL to run."
        )
        for item in items:
            if "test_local_run" in item.fspath.basename:
                if "integration" in item.keywords:
                    item.add_marker(skip_lmstudio)