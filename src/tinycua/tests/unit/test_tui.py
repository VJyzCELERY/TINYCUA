"""Tests for TUI widgets and application."""

import pytest


class TestOutputPanel:
    """Test OutputPanel widget."""

    def test_output_panel_initializes(self):
        """Test OutputPanel creates with empty content."""
        from tinycua.tui.widgets import OutputPanel

        panel = OutputPanel()
        assert panel._lines == []

    def test_output_panel_append_line(self):
        """Test appending lines to output panel."""
        from tinycua.tui.widgets import OutputPanel

        panel = OutputPanel()
        panel.append_line("hello")
        panel.append_line("world")

        assert len(panel._lines) == 2
        assert panel._lines[0] == "hello"
        assert panel._lines[1] == "world"

    def test_output_panel_clear(self):
        """Test clearing output panel."""
        from tinycua.tui.widgets import OutputPanel

        panel = OutputPanel()
        panel.append_line("test")
        panel.clear_output()

        assert panel._lines == []


class TestStatusBar:
    """Test StatusBar widget."""

    def test_status_bar_initializes(self):
        """Test StatusBar creates with default values."""
        from tinycua.tui.widgets import StatusBar

        bar = StatusBar()
        assert bar._status == "Disconnected"
        assert bar._agent == "none"
        assert bar._mode == "local"

    def test_status_bar_update_status(self):
        """Test updating status bar values."""
        from tinycua.tui.widgets import StatusBar

        bar = StatusBar()
        bar.update_status(status="Connected", agent="assistant", mode="local")

        assert bar._status == "Connected"
        assert bar._agent == "assistant"
        assert bar._mode == "local"

    def test_status_bar_partial_update(self):
        """Test updating only some status bar values."""
        from tinycua.tui.widgets import StatusBar

        bar = StatusBar()
        bar.update_status(status="Connected")

        assert bar._status == "Connected"
        assert bar._agent == "none"  # unchanged
        assert bar._mode == "local"  # unchanged


class TestTinyCUAApp:
    """Test TinyCUAApp application."""

    def test_app_initializes(self):
        """Test app creates with default values."""
        from tinycua.tui.app import TinyCUAApp

        app = TinyCUAApp()
        assert app._agent is None
        assert app._status_text == "Disconnected"
        assert app._agent_name == "none"

    def test_app_init_agent_success(self):
        """Test app initializes agent when available."""
        from tinycua.tui.app import TinyCUAApp

        mock_agent = type("MockAgent", (), {"name": "assistant"})()

        app = TinyCUAApp()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "tinycua.agent.default_agent.create_default_agent",
                lambda: mock_agent,
            )
            app._init_agent()

        assert app._agent is not None
        assert app._agent_name == "assistant"
        assert app._status_text == "Ready"

    def test_app_init_agent_failure(self):
        """Test app handles agent init failure gracefully."""
        from tinycua.tui.app import TinyCUAApp

        app = TinyCUAApp()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "tinycua.agent.default_agent.create_default_agent",
                lambda: (_ for _ in ()).throw(ImportError("No module")),
            )
            app._init_agent()

        assert app._agent is None
        assert "Error" in app._status_text
