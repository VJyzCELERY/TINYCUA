"""Tests for command parser."""

import pytest
from tinycua_sdk.tools.parser import CommandParser, ParsedCommand


class TestCommandParser:
    """Test CommandParser class."""

    def test_parse_simple_command(self):
        """Test parsing a simple command."""
        parser = CommandParser()
        result = parser.parse("ls")
        assert result.command == "ls"
        assert result.args == []
        assert result.flags == {}

    def test_parse_command_with_args(self):
        """Test parsing command with arguments."""
        parser = CommandParser()
        result = parser.parse("ls -la")
        assert result.command == "ls"
        assert result.args == []
        assert result.flags == {"la": ""}

    def test_parse_command_with_positional_args(self):
        """Test parsing command with positional arguments."""
        parser = CommandParser()
        result = parser.parse("echo hello world")
        assert result.command == "echo"
        assert result.args == ["hello", "world"]
        assert result.flags == {}

    def test_parse_command_with_key_value_flag(self):
        """Test parsing command with key=value flag."""
        parser = CommandParser()
        result = parser.parse("curl --url=https://example.com --output=file.txt")
        assert result.command == "curl"
        assert result.args == []
        assert result.flags == {"url": "https://example.com", "output": "file.txt"}

    def test_parse_command_with_boolean_flag(self):
        """Test parsing command with boolean flag."""
        parser = CommandParser()
        result = parser.parse("rm -rf /tmp")
        assert result.command == "rm"
        assert result.args == ["/tmp"]
        assert result.flags == {"rf": ""}

    def test_parse_empty_command_raises_error(self):
        """Test parsing empty command raises ValueError."""
        parser = CommandParser()
        with pytest.raises(ValueError):
            parser.parse("")

    def test_parse_quoted_args(self):
        """Test parsing quoted arguments."""
        parser = CommandParser()
        result = parser.parse('echo "hello world"')
        assert result.command == "echo"
        assert result.args == ["hello world"]

    def test_parse_complex_command(self):
        """Test parsing a complex command."""
        parser = CommandParser()
        result = parser.parse('python script.py --input=data.txt --verbose file1.txt file2.txt')
        assert result.command == "python"
        assert result.args == ["script.py", "file1.txt", "file2.txt"]
        assert result.flags == {"input": "data.txt", "verbose": ""}
