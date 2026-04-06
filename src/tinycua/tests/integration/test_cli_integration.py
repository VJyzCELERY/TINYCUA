"""Integration tests for CLI workflows."""

import argparse
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCLIRunIntegration:
    """Integration tests for the run command flow."""

    @pytest.mark.asyncio
    async def test_full_run_flow_with_mocked_agent(self):
        """Test full run command flow with mocked agent."""
        from tinycua.cli.commands import cmd_run

        args = argparse.Namespace(input="test input", file=None)

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Agent response"
        mock_agent.name = "assistant"

        with patch(
            "tinycua.agent.default_agent.create_default_agent", return_value=mock_agent
        ):
            result = await cmd_run(args)

        assert result == 0
        mock_agent.run.assert_called_once_with("test input")

    @pytest.mark.asyncio
    async def test_full_run_flow_with_file(self, tmp_path):
        """Test full run command flow with file input."""
        from tinycua.cli.commands import cmd_run

        script = tmp_path / "input.txt"
        script.write_text("file content")

        args = argparse.Namespace(input=None, file=str(script))

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Processed file"

        with patch(
            "tinycua.agent.default_agent.create_default_agent", return_value=mock_agent
        ):
            result = await cmd_run(args)

        assert result == 0
        mock_agent.run.assert_called_once_with("file content")


class TestCLIDeployIntegration:
    """Integration tests for the deploy command flow."""

    @pytest.mark.asyncio
    async def test_full_deploy_flow_with_mocked_backend(self):
        """Test full deploy command flow with mocked backend."""
        from tinycua.cli.commands import cmd_deploy

        args = argparse.Namespace(
            file=None,
            backend_url="http://localhost:8000",
            api_key="test-key",
        )

        mock_agent = MagicMock()
        mock_lifecycle = AsyncMock()
        mock_lifecycle.deploy.return_value = {
            "id": "deployed-agent-123",
            "status": "deployed",
        }

        with patch(
            "tinycua.agent.default_agent.create_default_agent", return_value=mock_agent
        ):
            with patch(
                "tinycua.agent.lifecycle.AgentLifecycle", return_value=mock_lifecycle
            ):
                result = await cmd_deploy(args)

        assert result == 0
        mock_lifecycle.deploy.assert_called_once()


class TestCLIChatIntegration:
    """Integration tests for the chat command flow."""

    @pytest.mark.asyncio
    async def test_full_chat_flow_with_quit(self):
        """Test full chat command flow with quit."""
        from tinycua.cli.commands import cmd_chat

        args = argparse.Namespace(agent=None)

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Hello!"

        with patch("tinycua.cli.commands.console") as mock_console:
            mock_console.input.side_effect = ["quit"]
            with patch(
                "tinycua.agent.default_agent.create_default_agent",
                return_value=mock_agent,
            ):
                result = await cmd_chat(args)

        assert result == 0


class TestCLITuiIntegration:
    """Integration tests for the TUI command flow."""

    @pytest.mark.asyncio
    async def test_tui_dispatch(self):
        """Test TUI command dispatches to Textual app."""
        from tinycua.cli.commands import cmd_tui

        args = argparse.Namespace()

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock()

        with patch("tinycua.tui.app.TinyCUAApp", return_value=mock_app):
            result = await cmd_tui(args)

        assert result == 0
        mock_app.run_async.assert_called_once()


class TestConfigLoadingInCLI:
    """Test config loading in CLI context."""

    @pytest.mark.asyncio
    async def test_run_loads_config(self):
        """Test run command loads user config."""
        from tinycua.cli.commands import cmd_run

        args = argparse.Namespace(input="test", file=None)

        mock_config = MagicMock()
        mock_config.llm.provider = "ollama"
        mock_config.llm.model = "llama3"
        mock_config.llm.base_url = "http://localhost:11434"
        mock_config.llm.api_key.get_secret_value.return_value = ""

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Response"

        with patch(
            "tinycua.agent.default_agent.create_default_agent", return_value=mock_agent
        ):
            result = await cmd_run(args)

        assert result == 0
