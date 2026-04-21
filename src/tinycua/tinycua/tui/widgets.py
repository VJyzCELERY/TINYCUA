#!/usr/bin/env python3
"""Custom Textual widgets for TinyCUA TUI."""

from __future__ import annotations

from textual.widgets import Static


class OutputPanel(Static):
    """Scrollable output display for agent responses.

    Provides a text area where agent output, tool calls, and errors
    are displayed in real-time.
    """

    DEFAULT_CSS = """
    OutputPanel {
        height: 1fr;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(self) -> None:
        """Initialize the output panel."""
        super().__init__()
        self._lines: list[str] = []

    def append_line(self, line: str) -> None:
        """Append a line to the output panel.

        Args:
            line: Text line to append.
        """
        self._lines.append(line)
        self.update("\n".join(self._lines))

    def clear_output(self) -> None:
        """Clear all output lines."""
        self._lines = []
        self.update("")


class StatusBar(Static):
    """Status bar showing connection and agent state.

    Displays current connection status, active agent name, and
    execution mode in the footer area.
    """

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary-darken-1;
        color: $text;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        """Initialize the status bar."""
        super().__init__()
        self._status = "Disconnected"
        self._agent = "none"
        self._mode = "local"

    def on_mount(self) -> None:
        """Initialize status bar content on mount."""
        self.render_content()

    def render_content(self) -> None:
        """Render the status bar content."""
        text = f"Status: {self._status} | Agent: {self._agent} | Mode: {self._mode}"
        self.update(text)

    def update_status(
        self,
        status: str | None = None,
        agent: str | None = None,
        mode: str | None = None,
    ) -> None:
        """Update status bar display.

        Args:
            status: Connection status text.
            agent: Current agent name.
            mode: Execution mode (local, deployed, guest).
        """
        if status is not None:
            self._status = status
        if agent is not None:
            self._agent = agent
        if mode is not None:
            self._mode = mode

        self.render_content()
