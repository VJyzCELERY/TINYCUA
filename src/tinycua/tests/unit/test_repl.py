"""Tests for tinycua REPL."""

from unittest.mock import patch


class TestREPL:
    """Test REPL functionality."""

    def test_run_repl_quit_command(self):
        """Test REPL exits on /quit command."""
        from tinycua.cli.repl import run_repl

        with patch("tinycua.cli.repl.PromptSession") as mock_session:
            mock_session.return_value.prompt.side_effect = ["/quit"]
            result = run_repl()

        assert result == 0

    def test_run_repl_help_command(self):
        """Test REPL shows help on /help command."""
        from tinycua.cli.repl import run_repl

        with patch("tinycua.cli.repl.PromptSession") as mock_session:
            mock_session.return_value.prompt.side_effect = ["/help", "/quit"]
            with patch("tinycua.cli.repl.console") as mock_console:
                result = run_repl()

        assert result == 0
        assert mock_console.print.call_count >= 2

    def test_run_repl_keyboard_interrupt(self):
        """Test REPL handles KeyboardInterrupt gracefully."""
        from tinycua.cli.repl import run_repl

        with patch("tinycua.cli.repl.PromptSession") as mock_session:
            mock_session.return_value.prompt.side_effect = [
                KeyboardInterrupt(),
                "/quit",
            ]
            result = run_repl()

        assert result == 0

    def test_run_repl_eof(self):
        """Test REPL handles EOFError gracefully."""
        from tinycua.cli.repl import run_repl

        with patch("tinycua.cli.repl.PromptSession") as mock_session:
            mock_session.return_value.prompt.side_effect = [EOFError()]
            result = run_repl()

        assert result == 0
