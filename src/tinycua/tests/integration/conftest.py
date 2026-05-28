"""Shared integration test fixtures for TinyCUA."""

import pytest


@pytest.fixture
def tui_app():
    """Create a TUI app instance for testing.

    Returns:
        TinyCUAApp instance for testing.
    """
    from tinycua.tui.app import TinyCUAApp

    app = TinyCUAApp()
    return app


@pytest.fixture
def sdk_agent():
    """Create an SDK agent instance for testing.

    Returns:
        Agent instance for testing.
    """
    from tinycua.agent.default_agent import create_default_agent

    agent = create_default_agent()
    return agent


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing.

    Args:
        tmp_path: Pytest tmp_path fixture for temporary directory.

    Returns:
        Database URL string for temporary SQLite database.
    """
    db_path = tmp_path / "test.db"
    return f"sqlite:///{db_path}"
