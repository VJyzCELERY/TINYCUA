"""Tests for command parsing - recognition, argument parsing, invalid commands."""

import pytest

from tinycua.cli.command_parser import CommandParser


class TestCommandRecognition:
    """Test command detection."""

    def test_help_command_recognized(self):
        """Test /help command is recognized."""
        parser = CommandParser()
        result = parser.parse("/help")
        assert result.command == "help"

    def test_new_command_recognized(self):
        """Test /new command is recognized."""
        parser = CommandParser()
        result = parser.parse("/new")
        assert result.command == "new"

    def test_list_command_recognized(self):
        """Test /list command is recognized."""
        parser = CommandParser()
        result = parser.parse("/list")
        assert result.command == "list"

    def test_quit_command_recognized(self):
        """Test /quit command is recognized."""
        parser = CommandParser()
        result = parser.parse("/quit")
        assert result.command == "quit"


class TestArgumentParsing:
    """Test argument handling."""

    def test_command_arguments_parsed(self):
        """Test command arguments are parsed correctly."""
        parser = CommandParser()
        result = parser.parse("/new my session")
        assert result.command == "new"
        assert result.args == ["my", "session"]

    def test_quoted_arguments_handled(self):
        """Test quoted arguments are handled."""
        parser = CommandParser()
        result = parser.parse('/new "my session name"')
        assert result.command == "new"
        assert "my session name" in result.args

    def test_multiple_arguments_handled(self):
        """Test multiple arguments are handled."""
        parser = CommandParser()
        result = parser.parse("/model qwen/qwen3.5-9b --temp 0.7")
        assert result.command == "model"
        assert "--temp" in result.args
        assert "0.7" in result.args


class TestInvalidCommandHandling:
    """Test error handling for invalid commands."""

    def test_unknown_command_handled(self):
        """Test unknown command is handled gracefully."""
        parser = CommandParser()
        result = parser.parse("/unknowncmd")
        assert result.is_valid is False
        assert "unknown" in result.error.lower()

    def test_malformed_command_handled(self):
        """Test malformed command is handled gracefully."""
        parser = CommandParser()
        result = parser.parse("/incomplete")
        assert result.is_valid is False

    def test_empty_command_handled(self):
        """Test empty command is handled gracefully."""
        parser = CommandParser()
        result = parser.parse("")
        assert result.is_valid is False
