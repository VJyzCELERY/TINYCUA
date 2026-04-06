"""Tests for REPL slash commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestREPLCommandHandler:
    """Test REPLCommandHandler methods."""

    def test_handler_initialization(self):
        """Test handler initializes with default values."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        assert handler._backend_url is None
        assert handler._backend_client is None
        assert handler._connected is False
        assert handler._chat_history == []

    @pytest.mark.asyncio
    async def test_handle_connect_success(self):
        """Test /connect with successful connection."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True

        with patch("tinycua.clients.backend.BackendClient", return_value=mock_client):
            result = await handler.handle_connect("http://localhost:8000")

        assert "Connected" in result
        assert handler._connected is True
        assert handler._backend_url == "http://localhost:8000"

    @pytest.mark.asyncio
    async def test_handle_connect_failure(self):
        """Test /connect with connection failure."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        with patch(
            "tinycua.clients.backend.BackendClient",
            side_effect=ConnectionError("Refused"),
        ):
            result = await handler.handle_connect("http://bad:8000")

        assert "Failed" in result
        assert handler._connected is False

    @pytest.mark.asyncio
    async def test_handle_status(self):
        """Test /status shows connection info."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()
        handler._backend_url = "http://localhost:8000"
        handler._connected = True
        handler._chat_history = [{"role": "user", "content": "hello"}]

        result = await handler.handle_status()

        assert "localhost:8000" in result
        assert "Yes" in result
        assert "1 turns" in result

    @pytest.mark.asyncio
    async def test_handle_agents_not_connected(self):
        """Test /agents when not connected."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        result = await handler.handle_agents()

        assert "Not connected" in result

    @pytest.mark.asyncio
    async def test_handle_agents_connected(self):
        """Test /agents lists agents from backend."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()
        handler._connected = True
        handler._backend_client = AsyncMock()
        handler._backend_client.list_agents.return_value = [
            {"name": "agent-1"},
            {"name": "agent-2"},
        ]

        result = await handler.handle_agents()

        assert "agent-1" in result
        assert "agent-2" in result

    @pytest.mark.asyncio
    async def test_handle_chat(self):
        """Test /chat starts chat session."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Hello!"

        with patch("tinycua.cli.repl.console") as mock_console:
            mock_console.input.side_effect = ["hello", "back"]
            with patch(
                "tinycua.agent.default_agent.create_default_agent",
                return_value=mock_agent,
            ):
                result = await handler.handle_chat("test-agent")

        assert "Chat session ended" in result
        assert len(handler._chat_history) == 2

    @pytest.mark.asyncio
    async def test_handle_chat_default_agent(self):
        """Test /chat without agent name defaults to assistant."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Hello!"

        with patch("tinycua.cli.repl.console") as mock_console:
            mock_console.input.side_effect = ["hello", "back"]
            with patch(
                "tinycua.agent.default_agent.create_default_agent",
                return_value=mock_agent,
            ):
                result = await handler.handle_chat("")

        assert "Chat session ended" in result

    @pytest.mark.asyncio
    async def test_handle_run_file_not_found(self):
        """Test /run with non-existent file."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        result = await handler.handle_run("/nonexistent/file.py")

        assert "File not found" in result

    @pytest.mark.asyncio
    async def test_handle_run_success(self, tmp_path):
        """Test /run with valid file."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        script_file = tmp_path / "script.txt"
        script_file.write_text("run this")

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Done!"

        with patch(
            "tinycua.agent.default_agent.create_default_agent", return_value=mock_agent
        ):
            result = await handler.handle_run(str(script_file))

        assert "Result:" in result
        mock_agent.run.assert_called_once_with("run this")

    @pytest.mark.asyncio
    async def test_handle_deploy(self):
        """Test /deploy deploys agent."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()
        handler._backend_url = "http://localhost:8000"

        mock_agent = MagicMock()
        mock_lifecycle = AsyncMock()
        mock_lifecycle.deploy.return_value = {"id": "agent-123"}

        with patch(
            "tinycua.agent.default_agent.create_default_agent", return_value=mock_agent
        ):
            with patch(
                "tinycua.agent.lifecycle.AgentLifecycle", return_value=mock_lifecycle
            ):
                result = await handler.handle_deploy("")

        assert "Deployed" in result
        assert "agent-123" in result

    def test_handle_help(self):
        """Test /help shows all commands."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        result = handler.handle_help()

        assert "/connect" in result
        assert "/status" in result
        assert "/agents" in result
        assert "/chat" in result
        assert "/run" in result
        assert "/deploy" in result
        assert "/help" in result
        assert "/quit" in result

    def test_handle_quit(self):
        """Test /quit exits cleanly."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        with patch("tinycua.cli.repl.console") as mock_console:
            handler.handle_quit()

        mock_console.print.assert_called()

    def test_handle_clear(self):
        """Test /clear clears the screen."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        with patch("tinycua.cli.repl.console") as mock_console:
            handler.handle_clear()

        mock_console.clear.assert_called_once()

    def test_handle_history_empty(self):
        """Test /history with no history."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        result = handler.handle_history()

        assert "No chat history" in result

    def test_handle_history_with_entries(self):
        """Test /history with chat entries."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()
        handler._chat_history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

        result = handler.handle_history()

        assert "Chat History" in result
        assert "hello" in result
        assert "hi there" in result


class TestSlashCommandParsing:
    """Test slash command parsing logic."""

    @pytest.mark.asyncio
    async def test_quit_returns_none(self):
        """Test /quit returns None to exit."""
        from tinycua.cli.repl import REPLCommandHandler, _handle_slash_command

        handler = REPLCommandHandler()
        result = await _handle_slash_command("/quit", handler)

        assert result is None

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        """Test unknown command returns error."""
        from tinycua.cli.repl import REPLCommandHandler, _handle_slash_command

        handler = REPLCommandHandler()
        result = await _handle_slash_command("/unknown", handler)

        assert result is not None
        assert "Unknown command" in result

    @pytest.mark.asyncio
    async def test_connect_requires_url(self):
        """Test /connect without URL shows usage."""
        from tinycua.cli.repl import REPLCommandHandler, _handle_slash_command

        handler = REPLCommandHandler()
        result = await _handle_slash_command("/connect", handler)

        assert result is not None
        assert "Usage:" in result

    @pytest.mark.asyncio
    async def test_run_requires_file(self):
        """Test /run without file shows usage."""
        from tinycua.cli.repl import REPLCommandHandler, _handle_slash_command

        handler = REPLCommandHandler()
        result = await _handle_slash_command("/run", handler)

        assert result is not None
        assert "Usage:" in result

    @pytest.mark.asyncio
    async def test_deploy_requires_file(self):
        """Test /deploy without file shows usage."""
        from tinycua.cli.repl import REPLCommandHandler, _handle_slash_command

        handler = REPLCommandHandler()
        result = await _handle_slash_command("/deploy", handler)

        assert result is not None
        assert "Usage:" in result

    @pytest.mark.asyncio
    async def test_chat_defaults_to_assistant(self):
        """Test /chat without agent name defaults to assistant."""
        from tinycua.cli.repl import REPLCommandHandler, _handle_slash_command

        handler = REPLCommandHandler()

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Hello!"

        with patch("tinycua.cli.repl.console") as mock_console:
            mock_console.input.side_effect = ["hello", "back"]
            with patch(
                "tinycua.agent.default_agent.create_default_agent",
                return_value=mock_agent,
            ):
                # Test /chat without argument defaults to "assistant"
                result = await _handle_slash_command("/chat", handler)

        assert "Chat session ended" in result


class TestREPLIntegration:
    """Test REPL integration with prompt-toolkit."""

    def test_slash_commands_list(self):
        """Test SLASH_COMMANDS contains all expected commands."""
        from tinycua.cli.repl import SLASH_COMMANDS

        expected = [
            "/connect",
            "/status",
            "/agents",
            "/chat",
            "/run",
            "/deploy",
            "/help",
            "/quit",
            "/clear",
            "/history",
        ]
        for cmd in expected:
            assert cmd in SLASH_COMMANDS

    def test_history_path_creation(self, tmp_path):
        """Test history path is created in ~/.tinycua/."""
        from tinycua.cli.repl import _get_history_path

        with patch("tinycua.cli.repl.Path") as mock_path:
            mock_home = tmp_path
            mock_path.home.return_value = mock_home
            mock_history_path = mock_home / ".tinycua" / "repl_history"

            _get_history_path()

            assert (mock_home / ".tinycua").exists()
