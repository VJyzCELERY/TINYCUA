"""Integration tests for REPL workflows."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestREPLCommandSequence:
    """Test full REPL command sequences."""

    @pytest.mark.asyncio
    async def test_connect_status_sequence(self):
        """Test connect then status command sequence."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True

        with patch("tinycua.clients.backend.BackendClient", return_value=mock_client):
            connect_result = await handler.handle_connect("http://localhost:8000")

        assert "Connected" in connect_result

        status_result = await handler.handle_status()
        assert "localhost:8000" in status_result
        assert "Yes" in status_result

    @pytest.mark.asyncio
    async def test_connect_agents_sequence(self):
        """Test connect then list agents sequence."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_agents.return_value = [
            {"name": "assistant"},
            {"name": "coder"},
        ]

        with patch("tinycua.clients.backend.BackendClient", return_value=mock_client):
            await handler.handle_connect("http://localhost:8000")

        agents_result = await handler.handle_agents()
        assert "assistant" in agents_result
        assert "coder" in agents_result

    @pytest.mark.asyncio
    async def test_full_command_sequence(self):
        """Test full command sequence: connect -> status -> agents -> help -> quit."""
        from tinycua.cli.repl import REPLCommandHandler, _handle_slash_command

        handler = REPLCommandHandler()

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.list_agents.return_value = [{"name": "assistant"}]

        with patch("tinycua.clients.backend.BackendClient", return_value=mock_client):
            # Connect
            result = await _handle_slash_command(
                "/connect http://localhost:8000", handler
            )
            assert "Connected" in result

            # Status
            result = await _handle_slash_command("/status", handler)
            assert "Connected" in result

            # Agents
            result = await _handle_slash_command("/agents", handler)
            assert "assistant" in result

            # Help
            result = _handle_slash_command("/help", handler)
            if hasattr(result, "__await__"):
                result = await result
            assert "/connect" in result

            # Quit
            result = await _handle_slash_command("/quit", handler)
            assert result is None


class TestREPLConfigLoading:
    """Test config loading in REPL context."""

    @pytest.mark.asyncio
    async def test_chat_uses_default_agent(self):
        """Test chat command creates default agent."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()

        mock_agent = AsyncMock()
        mock_agent.run.return_value = "Hello!"
        mock_agent.name = "test-agent"

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
    async def test_run_uses_default_agent(self, tmp_path):
        """Test run command creates default agent."""
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
    async def test_deploy_uses_default_agent(self):
        """Test deploy command creates default agent."""
        from tinycua.cli.repl import REPLCommandHandler

        handler = REPLCommandHandler()
        handler._backend_url = "http://localhost:8000"

        mock_agent = MagicMock()
        mock_lifecycle = AsyncMock()
        mock_lifecycle.deploy.return_value = {"id": "agent-456"}

        with patch(
            "tinycua.agent.default_agent.create_default_agent", return_value=mock_agent
        ):
            with patch(
                "tinycua.agent.lifecycle.AgentLifecycle", return_value=mock_lifecycle
            ):
                # Pass empty string to avoid file validation
                result = await handler.handle_deploy("")

        assert "Deployed" in result
        assert "agent-456" in result
