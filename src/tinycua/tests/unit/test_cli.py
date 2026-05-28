"""Tests for tinycua CLI entry point."""

import sys
from unittest.mock import AsyncMock, patch



class TestCLIMain:
    """Test CLI argument parsing and dispatch."""

    def test_main_shows_help_when_no_command(self, capsys):
        """Verify main prints help when no subcommand given."""
        from tinycua.cli.main import main

        with patch.object(sys, "argv", ["tinycua"]):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower() or "TINYCUA" in captured.out

    def test_main_repl_dispatch(self):
        """Verify main dispatches to REPL for 'repl' command."""
        from tinycua.cli.main import main

        with patch.object(sys, "argv", ["tinycua", "repl"]):
            with patch("tinycua.cli.repl.run_repl", return_value=0) as mock_repl:
                result = main()

        assert result == 0
        mock_repl.assert_called_once()

    def test_main_run_dispatch(self):
        """Verify main dispatches to cmd_run for 'run' command."""
        from tinycua.cli.main import main

        with patch.object(sys, "argv", ["tinycua", "run", "hello"]):
            with patch(
                "tinycua.cli.commands.cmd_run", new_callable=AsyncMock
            ) as mock_run:
                mock_run.return_value = 0
                result = main()

        assert result == 0
        mock_run.assert_called_once()

    def test_main_deploy_dispatch(self):
        """Verify main dispatches to cmd_deploy for 'deploy' command."""
        from tinycua.cli.main import main

        with patch.object(sys, "argv", ["tinycua", "deploy", "tools.py"]):
            with patch(
                "tinycua.cli.commands.cmd_deploy", new_callable=AsyncMock
            ) as mock_deploy:
                mock_deploy.return_value = 0
                result = main()

        assert result == 0
        mock_deploy.assert_called_once()

    def test_main_chat_dispatch(self):
        """Verify main dispatches to cmd_chat for 'chat' command."""
        from tinycua.cli.main import main

        with patch.object(sys, "argv", ["tinycua", "chat"]):
            with patch(
                "tinycua.cli.commands.cmd_chat", new_callable=AsyncMock
            ) as mock_chat:
                mock_chat.return_value = 0
                result = main()

        assert result == 0
        mock_chat.assert_called_once()

    def test_main_tui_dispatch(self):
        """Verify main dispatches to cmd_tui for 'tui' command."""
        from tinycua.cli.main import main

        with patch.object(sys, "argv", ["tinycua", "tui"]):
            with patch(
                "tinycua.cli.commands.cmd_tui", new_callable=AsyncMock
            ) as mock_tui:
                mock_tui.return_value = 0
                result = main()

        assert result == 0
        mock_tui.assert_called_once()
