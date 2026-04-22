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
from tinycua.remote import RemoteConnectionManager, SyncEngine
from tinycua.storage.local_storage import LocalStorageManager
from tinycua.tui.agent_manager import AgentManager
from tinycua.tui.chat import ChatInterface
from tinycua.tui.commands import CommandParser
from tinycua.tui.session_manager import TuiSessionManager
from tinycua.tui.skills_manager import SkillsManager
from tinycua.tui.tool_manager import ToolManager
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

    def __init__(
        self,
        session_manager: TuiSessionManager,
        agent_manager: AgentManager,
        tool_manager: ToolManager,
        skills_manager: SkillsManager,
    ) -> None:
        """Initialize the chat screen."""
        super().__init__()
        self._session_manager = session_manager
        self._agent_manager = agent_manager
        self._tool_manager = tool_manager
        self._skills_manager = skills_manager
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
            current_agent = self._agent_manager.get_current_agent()
            agent_name = current_agent.name if current_agent else "default"
            status_bar.update_status(
                status=self._status_text,
                agent=agent_name,
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
        args: str,
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
        elif command == "agents":
            agents = self._agent_manager.list_agents()
            if agents:
                lines = ["[bold]Available agents:[/bold]"]
                current = self._agent_manager.get_current_agent()
                for agent in agents:
                    marker = " *" if current and current.id == agent.id else ""
                    lines.append(f"  {agent.name} ({agent.config.model}){marker}")
                output.append_line("\n".join(lines))
            else:
                output.append_line("No agents configured. Use /agent-create to add one.")
        elif command == "agent":
            if not args:
                output.append_line("[yellow]Usage: /agent <name>[/yellow]")
                return
            agents = self._agent_manager.list_agents()
            target = None
            for agent in agents:
                if agent.name.lower() == args.lower():
                    target = agent
                    break
            if target:
                if self._agent_manager.set_current_agent(target.id):
                    agent_instance = self._agent_manager.create_agent_instance(target)
                    if agent_instance:
                        self.app._current_agent_instance = agent_instance
                        output.append_line(f"[green]Switched to agent: {target.name}[/green]")
                        self._update_status_bar()
                    else:
                        output.append_line("[red]Failed to create agent instance.[/red]")
                else:
                    output.append_line("[red]Failed to switch agent.[/red]")
            else:
                output.append_line(f"[red]Agent '{args}' not found.[/red]")
        elif command == "agent-create":
            if not args:
                output.append_line("[yellow]Usage: /agent-create <name> [--model gpt-5-nano] [--provider openai] [--base-url URL] [--api-key KEY] [--system-prompt PROMPT] [--instructions TEXT] [--temperature 1.0] [--max-turns N][/yellow]")
                return

            parts = args.split()
            name = parts[0]

            model = "gpt-5-nano"
            provider = "openai"
            base_url = None
            api_key = None
            system_prompt = "You are a helpful assistant."
            instructions = ""
            temperature = 1.0
            max_turns = None

            i = 1
            while i < len(parts):
                if parts[i] == "--model" and i + 1 < len(parts):
                    model = parts[i + 1]
                    i += 2
                elif parts[i] == "--provider" and i + 1 < len(parts):
                    provider = parts[i + 1]
                    i += 2
                elif parts[i] == "--base-url" and i + 1 < len(parts):
                    base_url = parts[i + 1]
                    i += 2
                elif parts[i] == "--api-key" and i + 1 < len(parts):
                    api_key = parts[i + 1]
                    i += 2
                elif parts[i] == "--system-prompt" and i + 1 < len(parts):
                    system_prompt = parts[i + 1]
                    i += 2
                elif parts[i] == "--instructions" and i + 1 < len(parts):
                    instructions = parts[i + 1]
                    i += 2
                elif parts[i] == "--temperature" and i + 1 < len(parts):
                    temperature = float(parts[i + 1])
                    i += 2
                elif parts[i] == "--max-turns" and i + 1 < len(parts):
                    max_turns = int(parts[i + 1])
                    i += 2
                else:
                    i += 1

            agent_info = self._agent_manager.create_agent(
                name,
                model=model,
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                system_prompt=system_prompt,
                instructions=instructions,
                temperature=temperature,
                max_turns=max_turns,
            )
            if agent_info:
                output.append_line(f"[green]Created agent: {agent_info.name}[/green]")
            else:
                output.append_line("[red]Failed to create agent.[/red]")
        elif command == "tools":
            tools = self._tool_manager.list_tools()
            if tools:
                lines = ["[bold]Available tools:[/bold]"]
                for tool in tools:
                    toolset = f" ({tool.toolset})" if tool.toolset else ""
                    lines.append(f"  {tool.name}{toolset}")
                output.append_line("\n".join(lines))
            else:
                output.append_line("No tools available.")
        elif command == "skills":
            skills = self._skills_manager.list_skills()
            if skills:
                lines = ["[bold]Available skills:[/bold]"]
                for skill in skills:
                    lines.append(f"  {skill.name} - {skill.description}")
                output.append_line("\n".join(lines))
            else:
                output.append_line("No skills available.")
        elif command == "reload-skills":
            if self._skills_manager.reload_skills():
                output.append_line("[green]Skills reloaded successfully.[/green]")
            else:
                output.append_line("[red]Failed to reload skills.[/red]")
        elif command == "connect":
            if not args:
                output.append_line("[yellow]Usage: /connect <backend_url> [--api-key KEY][/yellow]")
                return

            parts = args.split()
            backend_url = parts[0]
            api_key = None

            i = 1
            while i < len(parts):
                if parts[i] == "--api-key" and i + 1 < len(parts):
                    api_key = parts[i + 1]
                    i += 2
                else:
                    i += 1

            try:
                self.init_remote(backend_url, api_key)
                output.append_line(f"[green]Initialized remote connection to {backend_url}[/green]")
                output.append_line("[dim]Use /sync to sync with backend[/dim]")
            except Exception as e:
                output.append_line(f"[red]Failed to initialize remote connection: {e}[/red]")
        elif command == "sync":
            if not self._remote_manager:
                output.append_line("[red]Remote not initialized. Use /connect first.[/red]")
                return
            if not self._remote_manager.is_connected:
                output.append_line("[red]Not connected to remote. Use /connect first.[/red]")
                return
            try:
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(self._sync_engine.push_all())
                if result.success:
                    output.append_line(f"[green]Sync successful: {result.items_synced} items synced[/green]")
                else:
                    output.append_line(f"[red]Sync failed: {result.errors}[/red]")
            except Exception as e:
                output.append_line(f"[red]Sync error: {e}[/red]")

    async def _process_message(self, message: str, output: OutputPanel) -> None:
        """Process a chat message."""
        self._status_text = "Thinking..."
        self._update_status_bar()

        try:
            agent = self.app._current_agent_instance
            if agent is None:
                agent = self._agent_manager.get_default_agent()
            if agent is None:
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
        self._current_agent_instance: Any = None
        self._status_text = "Disconnected"
        self._agent_name = "none"
        self._mode = "local"
        self._storage_manager = LocalStorageManager.get_instance()
        self._session_manager = TuiSessionManager(self._storage_manager.get_store())
        self._command_parser = CommandParser()
        self._chat_interface = ChatInterface()
        self._agent_manager = AgentManager()
        self._tool_manager = ToolManager()
        self._skills_manager = SkillsManager()
        self._remote_manager: RemoteConnectionManager | None = None
        self._sync_engine: SyncEngine | None = None

    def on_mount(self) -> None:
        """Handle application mount event."""
        self._init_storage()
        self._init_agent()
        self._load_skills()
        self._create_default_session()
        self.push_screen(
            ChatScreen(
                self._session_manager,
                self._agent_manager,
                self._tool_manager,
                self._skills_manager,
            )
        )

    def _init_agent(self) -> None:
        """Initialize the default agent."""
        try:
            self._agent = self._agent_manager.init_default_agent()
            if self._agent:
                self._current_agent_instance = self._agent
                self._agent_name = self._agent.name
                self._status_text = "Ready"
                self._mode = "local"
            else:
                self._status_text = "Error: Agent init failed"
        except Exception as e:
            logger.exception("Failed to initialize agent")
            self._status_text = f"Error: {e}"

    def _load_skills(self) -> None:
        """Load skills on startup."""
        try:
            self._skills_manager.load_skills()
        except Exception:
            logger.exception("Failed to load skills")

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

    def _init_storage(self) -> None:
        """Initialize local storage on startup."""
        try:
            if self._storage_manager.initialize():
                logger.info("Local storage initialized")
            else:
                logger.warning("Failed to initialize local storage")
        except Exception:
            logger.exception("Error initializing storage")

    def init_remote(self, backend_url: str, api_key: str | None = None) -> None:
        """Initialize remote connection manager.

        Args:
            backend_url: URL of the remote backend
            api_key: Optional API key for authentication
        """
        self._remote_manager = RemoteConnectionManager(
            backend_url=backend_url,
            api_key=api_key,
        )
        self._sync_engine = SyncEngine(self._remote_manager)
        logger.info(f"Initialized remote manager for {backend_url}")

    async def _sync_with_backend(self) -> bool:
        """Sync data with remote backend.

        Returns:
            True if sync successful, False otherwise.
        """
        if not self._remote_manager or not self._sync_engine:
            logger.warning("Remote manager not initialized")
            return False

        if not self._remote_manager.is_connected:
            logger.warning("Not connected to remote backend")
            return False

        try:
            result = await self._sync_engine.push_all()
            if result.success:
                self._status_text = f"Synced {result.items_synced} items"
                return True
            else:
                self._status_text = f"Sync failed: {result.errors}"
                return False
        except Exception:
            logger.exception("Sync failed")
            return False

    def get_remote_manager(self) -> RemoteConnectionManager | None:
        """Get the remote connection manager."""
        return self._remote_manager

    def get_session_manager(self) -> TuiSessionManager:
        """Get the session manager."""
        return self._session_manager

    def get_agent_manager(self) -> AgentManager:
        """Get the agent manager."""
        return self._agent_manager

    def get_tool_manager(self) -> ToolManager:
        """Get the tool manager."""
        return self._tool_manager

    def get_skills_manager(self) -> SkillsManager:
        """Get the skills manager."""
        return self._skills_manager

    def get_storage_manager(self) -> LocalStorageManager:
        """Get the storage manager."""
        return self._storage_manager

    def get_command_parser(self) -> CommandParser:
        """Get the command parser."""
        return self._command_parser
