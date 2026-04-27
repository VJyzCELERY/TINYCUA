"""Command parser for TinyCUA TUI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedCommand:
    """Represents a parsed command.

    Attributes:
        name: Command name.
        args: Command arguments.
    """

    name: str
    args: str


class CommandParser:
    """Slash command parser for TUI.

    Recognizes commands like /help, /new, /list, /quit, /clear, /settings
    and parses their arguments.
    """

    def __init__(self) -> None:
        """Initialize command parser with built-in commands."""
        self._commands: dict[str, str] = {
            "help": "Show available commands",
            "new": "Start a new chat session",
            "list": "List all sessions",
            "quit": "Exit the application",
            "clear": "Clear the current chat",
            "settings": "Open settings",
            "agents": "List all agents",
            "agent": "Switch to an agent (usage: /agent <name>)",
            "agent-create": "Create a new agent (usage: /agent-create <name>)",
            "tools": "List all available tools",
            "skills": "List all available skills",
            "reload-skills": "Reload skills from directories",
            "export": "Export data to file (usage: /export [path] [--no-sessions] [--no-agents] [--no-memory] [--no-skills])",
            "import": "Import data from file (usage: /import [path] [--mode merge|replace]). Note: skill files must be installed manually; only metadata is imported.",
        }

    def parse(self, text: str) -> ParsedCommand | None:
        """Parse text into a command.

        Args:
            text: Input text to parse.

        Returns:
            ParsedCommand if valid slash command, None otherwise.
        """
        text = text.strip()
        if not text.startswith("/"):
            return None

        parts = text[1:].split(maxsplit=1)
        command_name = parts[0].lower()

        if command_name not in self._commands:
            if command_name in ("agent",):
                return ParsedCommand(
                    name=command_name, args=parts[1] if len(parts) > 1 else ""
                )
            return None

        args = parts[1] if len(parts) > 1 else ""
        return ParsedCommand(name=command_name, args=args)

    def is_command(self, text: str) -> bool:
        """Check if text is a command.

        Args:
            text: Input text.

        Returns:
            True if text is a valid command.
        """
        parsed = self.parse(text)
        return parsed is not None

    def get_help(self, command_name: str) -> str | None:
        """Get help text for a command.

        Args:
            command_name: Command name.

        Returns:
            Help text or None if command not found.
        """
        return self._commands.get(command_name.lower())

    def get_all_commands(self) -> dict[str, str]:
        """Get all available commands.

        Returns:
            Dictionary of command names to descriptions.
        """
        return self._commands.copy()

    def get_help_text(self) -> str:
        """Get formatted help text for all commands.

        Returns:
            Formatted help string.
        """
        lines = ["Available commands:"]
        for name, description in self._commands.items():
            lines.append(f"  /{name} - {description}")
        return "\n".join(lines)
