"""Tests for TUI command parser."""

import pytest


class TestCommandParser:
    """Test CommandParser class."""

    def test_command_parser_initializes(self):
        """Test command parser initializes."""
        from tinycua.tui.commands import CommandParser

        parser = CommandParser()
        assert parser._commands != {}

    def test_command_parser_recognizes_slash_command(self):
        """Test parser recognizes slash commands."""
        from tinycua.tui.commands import CommandParser

        parser = CommandParser()
        result = parser.parse("/help")
        
        assert result is not None
        assert result.name == "help"

    def test_command_parser_parses_command_with_args(self):
        """Test parsing command with arguments."""
        from tinycua.tui.commands import CommandParser

        parser = CommandParser()
        result = parser.parse("/new My Session")
        
        assert result is not None
        assert result.name == "new"
        assert result.args == "My Session"

    def test_command_parser_returns_none_for_regular_text(self):
        """Test non-command text returns None."""
        from tinycua.tui.commands import CommandParser

        parser = CommandParser()
        result = parser.parse("Hello world")
        
        assert result is None

    def test_command_parser_handles_unknown_command(self):
        """Test unknown command returns None."""
        from tinycua.tui.commands import CommandParser

        parser = CommandParser()
        result = parser.parse("/unknowncommand")
        
        assert result is None

    def test_command_parser_gets_help_text(self):
        """Test getting help text for command."""
        from tinycua.tui.commands import CommandParser

        parser = CommandParser()
        help_text = parser.get_help("help")
        
        assert help_text is not None
        assert "available" in help_text.lower() or "command" in help_text.lower()

    def test_command_parser_gets_all_commands(self):
        """Test getting all available commands."""
        from tinycua.tui.commands import CommandParser

        parser = CommandParser()
        commands = parser.get_all_commands()
        
        assert "help" in commands
        assert "new" in commands
        assert "list" in commands
        assert "quit" in commands
        assert "clear" in commands

    def test_command_parser_strips_whitespace(self):
        """Test parsing strips whitespace."""
        from tinycua.tui.commands import CommandParser

        parser = CommandParser()
        result = parser.parse("  /help  ")
        
        assert result is not None
        assert result.name == "help"


class TestParsedCommand:
    """Test ParsedCommand dataclass."""

    def test_parsed_command_creation(self):
        """Test creating a parsed command."""
        from tinycua.tui.commands import ParsedCommand

        cmd = ParsedCommand(name="help", args="")
        
        assert cmd.name == "help"
        assert cmd.args == ""

    def test_parsed_command_with_args(self):
        """Test parsed command with arguments."""
        from tinycua.tui.commands import ParsedCommand

        cmd = ParsedCommand(name="new", args="My Session")
        
        assert cmd.name == "new"
        assert cmd.args == "My Session"
