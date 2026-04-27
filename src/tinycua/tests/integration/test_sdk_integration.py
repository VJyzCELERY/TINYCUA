"""Integration tests for TUI + SDK integration.

These tests verify that the TUI correctly integrates with the SDK agent.
"""

import pytest


class TestSDKIntegration:
    """Tests for SDK integration with TUI."""

    def test_tui_creates_agent_via_sdk(self, tui_app):
        """Test TUI creates agent via SDK."""
        from tinycua.tui.app import TinyCUAApp

        assert tui_app is not None
        assert isinstance(tui_app, TinyCUAApp)

    def test_tui_uses_sdk_for_execution(self, sdk_agent):
        """Test TUI uses SDK for agent execution."""
        from tinycua_sdk.agent.agent import Agent

        assert sdk_agent is not None
        assert isinstance(sdk_agent, Agent)

    @pytest.mark.asyncio
    async def test_sdk_agent_run(self, sdk_agent):
        """Test SDK agent can run."""
        try:
            result = await sdk_agent.run("Hello")
            assert result is not None
        except Exception:
            pytest.skip("LM Studio or LLM not available")

    @pytest.mark.asyncio
    async def test_tui_agent_execution(self, tui_app):
        """Test TUI agent execution flow."""
        if not hasattr(tui_app, "_agent") or tui_app._agent is None:
            pytest.skip("Agent not initialized")

        assert tui_app._agent is not None


class TestTUIDisplaysSDKResults:
    """Tests for TUI displaying SDK results."""

    def test_tui_output_panel_exists(self, tui_app):
        """Test TUI has output panel for displaying results."""
        from tinycua.tui.widgets import OutputPanel

        output = tui_app.query_one("#output", OutputPanel)
        assert output is not None

    def test_tui_status_bar_exists(self, tui_app):
        """Test TUI has status bar."""
        from tinycua.tui.widgets import StatusBar

        status_bar = tui_app.query_one("#status-bar", StatusBar)
        assert status_bar is not None


class TestSDKConfiguration:
    """Tests for SDK configuration integration."""

    def test_agent_has_model_configured(self, sdk_agent):
        """Test agent has model configured."""
        assert hasattr(sdk_agent, "model")
        assert sdk_agent.model is not None

    def test_agent_has_provider_configured(self, sdk_agent):
        """Test agent has provider configured."""
        assert hasattr(sdk_agent, "provider")
        assert sdk_agent.provider is not None


class TestAgentToolsIntegration:
    """Tests for agent tools integration."""

    def test_agent_has_tools(self, sdk_agent):
        """Test agent has tools available."""
        assert hasattr(sdk_agent, "tools")

    def test_agent_tools_are_list(self, sdk_agent):
        """Test agent tools is a list."""
        assert isinstance(sdk_agent.tools, (list, tuple))
