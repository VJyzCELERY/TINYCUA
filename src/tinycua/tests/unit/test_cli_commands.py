"""Tests for CLI command handlers."""

import argparse
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCmdRun:
    """Test cmd_run command handler."""

    @pytest.mark.asyncio
    async def test_run_with_input_string(self):
        """Test run command with direct input string."""
        from tinycua.cli.commands import cmd_run

        args = argparse.Namespace(input="hello world", file=None)

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Hello! How can I help?"

        with patch(
            "tinycua.agent.default_agent.create_default_agent", return_value=mock_agent
        ):
            result = await cmd_run(args)

        assert result == 0
        mock_agent.run.assert_called_once_with("hello world")

    @pytest.mark.asyncio
    async def test_run_with_file(self, tmp_path):
        """Test run command with script file."""
        from tinycua.cli.commands import cmd_run

        script_file = tmp_path / "script.txt"
        script_file.write_text("run this script")

        args = argparse.Namespace(input=None, file=str(script_file))

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Script executed"

        with patch(
            "tinycua.agent.default_agent.create_default_agent", return_value=mock_agent
        ):
            result = await cmd_run(args)

        assert result == 0
        mock_agent.run.assert_called_once_with("run this script")

    @pytest.mark.asyncio
    async def test_run_missing_file(self):
        """Test run command with non-existent file."""
        from tinycua.cli.commands import cmd_run

        args = argparse.Namespace(input=None, file="/nonexistent/file.py")

        result = await cmd_run(args)

        assert result == 1

    @pytest.mark.asyncio
    async def test_run_no_input(self):
        """Test run command with no input or file."""
        from tinycua.cli.commands import cmd_run

        args = argparse.Namespace(input=None, file=None)

        result = await cmd_run(args)

        assert result == 1


class TestCmdDeploy:
    """Test cmd_deploy command handler."""

    @pytest.mark.asyncio
    async def test_deploy_success(self):
        """Test deploy command succeeds."""
        from tinycua.cli.commands import cmd_deploy

        args = argparse.Namespace(
            file=None,
            backend_url="http://localhost:8000",
            api_key="test-key",
        )

        mock_agent = MagicMock()
        mock_lifecycle = AsyncMock()
        mock_lifecycle.deploy.return_value = {
            "id": "agent-123",
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

    @pytest.mark.asyncio
    async def test_deploy_backend_error(self):
        """Test deploy command handles backend errors."""
        from tinycua.cli.commands import cmd_deploy

        args = argparse.Namespace(
            file=None,
            backend_url="http://localhost:8000",
            api_key="test-key",
        )

        mock_agent = MagicMock()
        mock_lifecycle = AsyncMock()
        mock_lifecycle.deploy.side_effect = OSError("Backend unavailable")

        with patch(
            "tinycua.agent.default_agent.create_default_agent", return_value=mock_agent
        ):
            with patch(
                "tinycua.agent.lifecycle.AgentLifecycle", return_value=mock_lifecycle
            ):
                result = await cmd_deploy(args)

        assert result == 1


class TestCmdChat:
    """Test cmd_chat command handler."""

    @pytest.mark.asyncio
    async def test_chat_quit(self):
        """Test chat command exits on quit."""
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

    @pytest.mark.asyncio
    async def test_chat_with_message(self):
        """Test chat command processes a message then quits."""
        from tinycua.cli.commands import cmd_chat

        args = argparse.Namespace(agent=None)

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Hello back!"

        with patch("tinycua.cli.commands.console") as mock_console:
            mock_console.input.side_effect = ["hello", "quit"]
            with patch(
                "tinycua.agent.default_agent.create_default_agent",
                return_value=mock_agent,
            ):
                result = await cmd_chat(args)

        assert result == 0
        mock_agent.run.assert_called_once_with("hello")


class TestCmdTui:
    """Test cmd_tui command handler."""

    @pytest.mark.asyncio
    async def test_tui_launch(self):
        """Test tui command launches Textual app."""
        from tinycua.cli.commands import cmd_tui

        args = argparse.Namespace()

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock()

        with patch("tinycua.tui.app.TinyCUAApp", return_value=mock_app):
            result = await cmd_tui(args)

        assert result == 0
        mock_app.run_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_tui_import_error(self):
        """Test tui command handles missing Textual gracefully."""
        from tinycua.cli.commands import cmd_tui

        args = argparse.Namespace()

        with patch(
            "tinycua.tui.app.TinyCUAApp",
            side_effect=ImportError("No module named textual"),
        ):
            result = await cmd_tui(args)

        assert result == 1
