from typing import List, Optional
from dataclasses import dataclass
import shlex


VALID_COMMANDS = ["help", "new", "list", "quit", "model", "load", "save", "exit", "clear", "status"]


@dataclass
class ParseResult:
    command: str
    args: List[str]
    is_valid: bool
    error: Optional[str] = None


class CommandParser:
    """Parser for CLI commands."""

    def __init__(self):
        self.valid_commands = VALID_COMMANDS

    def parse(self, input_str: str) -> ParseResult:
        """Parse a command string."""
        if not input_str or not input_str.strip():
            return ParseResult(
                command="",
                args=[],
                is_valid=False,
                error="Empty command"
            )

        if not input_str.startswith("/"):
            return ParseResult(
                command="",
                args=[],
                is_valid=False,
                error="Commands must start with /"
            )

        try:
            parts = shlex.split(input_str[1:])
        except ValueError:
            parts = input_str[1:].split()

        if not parts:
            return ParseResult(
                command="",
                args=[],
                is_valid=False,
                error="No command specified"
            )

        command = parts[0]
        args = parts[1:]

        if command not in self.valid_commands:
            return ParseResult(
                command=command,
                args=args,
                is_valid=False,
                error=f"Unknown command: {command}"
            )

        return ParseResult(
            command=command,
            args=args,
            is_valid=True
        )
