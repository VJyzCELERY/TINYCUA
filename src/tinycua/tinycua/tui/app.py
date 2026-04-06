"""Main Textual TUI application for TinyCUA."""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Input

from tinycua.tui.widgets import OutputPanel, StatusBar


class TinyCUAApp(App):
    """Main Textual TUI application.

    Provides an interactive terminal UI for agent interaction with
    streaming output, input panel, and status bar.
    """

    TITLE = "TinyCUA"
    SUB_TITLE = "Computer-Use Agent"

    CSS = """
    Screen {
        layout: vertical;
    }

    #output-container {
        height: 1fr;
    }

    #input-container {
        height: 3;
        dock: bottom;
        layout: horizontal;
    }

    #input-container Input {
        width: 1fr;
    }

    #input-container Button {
        width: 10;
    }
    """

    def __init__(self) -> None:
        """Initialize the TUI application."""
        super().__init__()
        self._agent: Any = None
        self._status_text = "Disconnected"
        self._agent_name = "none"
        self._mode = "local"

    def compose(self) -> ComposeResult:
        """Compose the TUI layout.

        Returns:
            ComposeResult with Header, OutputPanel, Input, StatusBar, Footer.
        """
        yield Header()
        yield OutputPanel(id="output")
        yield Container(
            Input(placeholder="Type a message...", id="input"),
            id="input-container",
        )
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Handle application mount event."""
        self._init_agent()
        self._update_status_bar()
        output = self.query_one("#output", OutputPanel)
        output.append_line("[bold green]Welcome to TinyCUA TUI[/bold green]")
        output.append_line("Type a message and press Enter to chat.")
        output.append_line("Type 'quit' to exit.\n")

    def _init_agent(self) -> None:
        """Initialize the default agent."""
        try:
            from tinycua.agent.default_agent import create_default_agent

            self._agent = create_default_agent()
            self._agent_name = self._agent.name
            self._status_text = "Ready"
            self._mode = "local"
        except Exception as e:
            self._status_text = f"Error: {e}"

    def _update_status_bar(self) -> None:
        """Update the status bar with current state."""
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.update_status(
                status=self._status_text,
                agent=self._agent_name,
                mode=self._mode,
            )
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission.

        Args:
            event: Input submission event containing user text.
        """
        user_input = event.value.strip()
        if not user_input:
            return

        output = self.query_one("#output", OutputPanel)
        output.append_line(f"[bold blue]You>[/bold blue] {user_input}")

        if user_input.lower() in ("quit", "exit"):
            output.append_line("[yellow]Goodbye![/yellow]")
            self.exit()
            return

        if not self._agent:
            output.append_line("[red]Agent not available.[/red]")
            return

        self._status_text = "Thinking..."
        self._update_status_bar()

        try:
            result = await self._agent.run(user_input)
            output.append_line(f"[green]Assistant: {result}[/green]")
            self._status_text = "Ready"
        except Exception as e:
            output.append_line(f"[red]Error: {e}[/red]")
            self._status_text = "Error"

        self._update_status_bar()

        # Clear input
        input_widget = self.query_one("#input", Input)
        input_widget.value = ""
