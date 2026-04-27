"""Tests for agent loop module."""

from tinycua_sdk.agent.loop import DefaultLoop


class TestAgentLoop:
    """Test agent loop."""

    def test_loop_import(self):
        """Test loop can be imported."""
        from tinycua_sdk.agent import loop

        assert loop is not None

    def test_default_loop_class(self):
        """Test DefaultLoop class exists."""
        assert DefaultLoop is not None

    def test_default_loop_init(self):
        """Test DefaultLoop initialization."""
        loop = DefaultLoop()
        assert loop is not None
