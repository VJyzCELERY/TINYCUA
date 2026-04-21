#!/usr/bin/env python3
"""Main Textual TUI application for TinyCUA."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Any

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static

from tinycua.agent.default_agent import create_default_agent
from tinycua.tui.chat import ChatInterface
from tinycua.tui.commands import CommandParser
from tinycua.tui.session_manager import TuiSessionManager
from tinycua.tui.widgets import OutputPanel, StatusBar

if TYPE_CHECKING:
    from textual.events import Key

logger = logging.getLogger(__name__)

SHARED_CSS = """
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
"""


class ChatScreen(Screen):
    """Main chat screen with message input and output."""

    CSS = SHARED_CSS

    def __init__(self, session_manager: TuiSessionManager) -> None:
        """Initialize the chat screen."""
        super().__init__()
        self._session_manager = session_manager
        self._chat_interface = ChatInterface()
        self._command_parser = CommandParser()
        self._status_text = "Ready"

    def compose(self) -> ComposeResult:
        """Compose the chat screen layout."""
        yield Header()
        yield Container(
            OutputPanel(id="output"),
            id="output-container",
        )
        yield Container(
            Input(placeholder="Type a message or /command...", id="input"),
            id="input-container",
        )
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount event."""
        self._update_status_bar()
        output = self.query_one("#output", OutputPanel)
        session = self._session_manager.get_current_session()
        if session:
            output.append_line(f"[dim]Session: {session.name}[/dim]")
        output.append_line("[bold green]Welcome to TinyCUA![/bold green]")
        output.append_line("Type a message or /help for commands.")

    def _update_status_bar(self) -> None:
        """Update the status bar with current state."""
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.update_status(
                status=self._status_text,
                agent="default",
                mode="local",
            )
        except Exception:
            logger.exception("Failed to update status bar")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        user_input = event.value.strip()
        if not user_input:
            return

        output = self.query_one("#output", OutputPanel)
        output.append_line(f"[bold blue]You>[/bold blue] {user_input}")

        parsed = self._command_parser.parse(user_input)
        if parsed:
            await self._handle_command(parsed.name, parsed.args, output)
            input_widget = self.query_one("#input", Input)
            input_widget.value = ""
            return

        if user_input.lower() in ("quit", "exit"):
            output.append_line("[yellow]Goodbye![/yellow]")
            self.app.exit()
            return

        self._chat_interface.add_user_message(user_input)
        await self._process_message(user_input, output)

        input_widget = self.query_one("#input", Input)
        input_widget.value = ""

    async def _handle_command(
        self,
        command: str,
        _args: str,
        output: OutputPanel,
    ) -> None:
        """Handle slash commands."""
        if command == "help":
            help_text = self._command_parser.get_help_text()
            output.append_line(help_text)
        elif command == "new":
            session = self._session_manager.create_session("Session")
            if session:
                output.append_line(
                    f"[green]Created new session: {session.name}[/green]",
                )
            else:
                output.append_line("[red]Failed to create session.[/red]")
        elif command == "list":
            sessions = self._session_manager.list_sessions()
            if sessions:
                lines = ["[bold]Available sessions:[/bold]"]
                for s in sessions:
                    current = (
                        " *"
                        if s.id == self._session_manager.get_current_session_id()
                        else ""
                    )
                    lines.append(f"  {s.name}{current}")
                output.append_line("\n".join(lines))
            else:
                output.append_line("No sessions available.")
        elif command == "clear":
            output.clear_output()
            self._chat_interface.clear()
            output.append_line("[dim]Output cleared.[/dim]")
        elif command == "settings":
            self.app.push_screen(SettingsScreen())
        elif command == "quit":
            output.append_line("[yellow]Goodbye![/yellow]")
            self.app.exit()

    async def _process_message(self, message: str, output: OutputPanel) -> None:
        """Process a chat message."""
        self._status_text = "Thinking..."
        self._update_status_bar()

        try:
            agent = create_default_agent()
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: agent.run(message))
            if isinstance(result, str):
                output.append_line(f"[green]Assistant: {result}[/green]")
                self._chat_interface.add_assistant_message(result)
            else:
                output.append_line(f"[green]Assistant: {result}[/green]")
                self._chat_interface.add_assistant_message(str(result))
            self._status_text = "Ready"
        except Exception as e:
            logger.exception("Failed to process message")
            output.append_line(f"[red]Error: {e}[/red]")
            self._status_text = "Error"

        self._update_status_bar()

    def on_key(self, event: Key) -> None:
        """Handle key events for input history navigation."""
        if event.key == "up":
            prev_input = self._chat_interface.get_previous_input()
            if prev_input is not None:
                input_widget = self.query_one("#input", Input)
                input_widget.value = prev_input
        elif event.key == "down":
            next_input = self._chat_interface.get_next_input()
            if next_input is not None:
                input_widget = self.query_one("#input", Input)
                input_widget.value = next_input


class SessionsListScreen(Screen):
    """Sessions list and management screen."""

    CSS = """
    SessionsListScreen {
        align: center middle;
    }

    #sessions-container {
        width: 50;
        height: auto;
        border: solid $primary;
        padding: 2;
    }

    .session-button {
        width: 100%;
        margin: 1 0;
    }
    """

    def __init__(self, session_manager: TuiSessionManager) -> None:
        """Initialize the sessions screen."""
        super().__init__()
        self._session_manager = session_manager

    def compose(self) -> ComposeResult:
        """Compose the sessions screen layout."""
        yield Container(
            Static("[bold]Sessions[/bold]", id="title"),
            Vertical(id="sessions-list"),
            Button("New Session", id="btn-new"),
            Button("Back to Chat", id="btn-back"),
            id="sessions-container",
        )

    def on_mount(self) -> None:
        """Handle screen mount."""
        self._populate_sessions()

    def _populate_sessions(self) -> None:
        """Populate sessions list."""
        container = self.query_one("#sessions-list", Vertical)
        container.remove_children()

        sessions = self._session_manager.list_sessions()
        current_id = self._session_manager.get_current_session_id()

        if not sessions:
            container.mount(Static("No sessions available."))
        else:
            for session in sessions:
                label = f"{session.name}"
                if session.id == current_id:
                    label += " *"
                container.mount(
                    Button(
                        label,
                        id=f"btn-session-{session.id}",
                        classes="session-button",
                    ),
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        if not button_id:
            return

        if button_id == "btn-new":
            session = self._session_manager.create_session("New Session")
            if session:
                self._populate_sessions()
        elif button_id == "btn-back":
            self.app.pop_screen()
        elif button_id.startswith("btn-session-"):
            session_id_str = button_id.replace("btn-session-", "")
            try:
                session_id = uuid.UUID(session_id_str)
                self._session_manager.resume_session(session_id)
                self.app.pop_screen()
            except ValueError:
                logger.exception("Invalid session ID format")
            except Exception:
                logger.exception("Failed to resume session")


class SettingsScreen(Screen):
    """Settings display screen."""

    CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 50;
        height: auto;
        border: solid $primary;
        padding: 2;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the settings screen layout."""
        yield Container(
            Static("[bold]Settings[/bold]", id="title"),
            Static(
                "Mode: local\nAgent: default\nTheme: default\nAuto-save: enabled",
                id="settings-content",
            ),
            Button("Back", id="btn-back"),
            id="settings-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-back":
            self.app.pop_screen()


class HelpScreen(Screen):
    """Help display screen."""

    CSS = """
    HelpScreen {
        align: center middle;
    }

    #help-container {
        width: 60;
        height: auto;
        border: solid $primary;
        padding: 2;
    }
    """

    def __init__(self, command_parser: CommandParser) -> None:
        """Initialize the help screen."""
        super().__init__()
        self._command_parser = command_parser

    def compose(self) -> ComposeResult:
        """Compose the help screen layout."""
        help_text = self._command_parser.get_help_text()
        yield Container(
            Static("[bold]Help[/bold]", id="title"),
            Static(help_text, id="help-content"),
            Button("Back", id="btn-back"),
            id="help-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-back":
            self.app.pop_screen()


class TinyCUAApp(App):
    """Main Textual TUI application.

    Provides an interactive terminal UI for agent interaction with
    streaming output, input panel, and status bar.
    """

    TITLE = "TinyCUA"
    SUB_TITLE = "Computer-Use Agent"

    CSS = SHARED_CSS

    def __init__(self) -> None:
        """Initialize the TUI application."""
        super().__init__()
        self._agent: Any = None
        self._status_text = "Disconnected"
        self._agent_name = "none"
        self._mode = "local"
        self._session_manager = TuiSessionManager(None)
        self._command_parser = CommandParser()
        self._chat_interface = ChatInterface()

    def on_mount(self) -> None:
        """Handle application mount event."""
        self._init_agent()
        self._create_default_session()
        self.push_screen(ChatScreen(self._session_manager))

    def _init_agent(self) -> None:
        """Initialize the default agent."""
        try:
            self._agent = create_default_agent()
            self._agent_name = self._agent.name
            self._status_text = "Ready"
            self._mode = "local"
        except Exception as e:
            logger.exception("Failed to initialize agent")
            self._status_text = f"Error: {e}"

    def _create_default_session(self) -> None:
        """Create a default session on startup."""
        try:
            sessions = self._session_manager.list_sessions()
            if not sessions:
                self._session_manager.create_session("Default Session")
            else:
                self._session_manager.set_current_session(sessions[0].id)
        except Exception:
            logger.exception("Failed to create default session")

    def get_session_manager(self) -> TuiSessionManager:
        """Get the session manager."""
        return self._session_manager

    def get_command_parser(self) -> CommandParser:
        """Get the command parser."""
        return self._command_parser
