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
    pass