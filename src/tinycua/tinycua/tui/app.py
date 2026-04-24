#!/usr/bin/env python3
"""Main Textual TUI application for TinyCUA."""

from __future__ import annotations

import asyncio
import datetime
import logging
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    SelectionList,
    Static,
)

from tinycua.agent.default_agent import create_default_agent
from tinycua.remote import RemoteConnectionManager, SyncEngine
from tinycua.storage import ExportManager, ExportOptions, ImportManager, ImportMode
from tinycua.storage.local_memory_store import LocalMemoryStore
from tinycua.storage.local_session_store import LocalSessionStore
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


_DEFAULT_EXPORT_DIR = Path.home() / ".tinycua"


def _validate_path(
    path: Path, *, must_exist: bool = False, allow_create_dir: bool = True
) -> tuple[bool, str]:
    """Validate a user-provided path for traversal safety.

    Args:
        path: The path to validate.
        must_exist: Whether the path must already exist.
        allow_create_dir: Whether missing parent directories may be created.

    Returns:
        Tuple of (is_valid, error_message).
    """
    try:
        resolved = path.resolve()
    except OSError as e:
        return False, f"Invalid path: {e}"

    # Reject paths with .. components after normalization
    normalized = path.expanduser().resolve()
    if ".." in path.parts:
        return False, "Path cannot contain parent directory references (..)"

    # Ensure the path is within an allowed base directory
    allowed_bases = [
        Path.home().resolve(),
        Path("/tmp").resolve(),
        Path(tempfile.gettempdir()).resolve(),
    ]

    # Also allow the default export directory
    allowed_bases.append(_DEFAULT_EXPORT_DIR.resolve())

    in_allowed = any(normalized.is_relative_to(base) for base in allowed_bases)
    if not in_allowed:
        return (
            False,
            f"Path must be within home, temp, or {_DEFAULT_EXPORT_DIR}",
        )

    if must_exist and not resolved.exists():
        return False, f"Path does not exist: {path}"

    if not must_exist and not allow_create_dir:
        if not resolved.parent.exists():
            return False, f"Parent directory does not exist: {resolved.parent}"

    return True, ""


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
        """Handle slash commands via dispatch table."""
        handler = getattr(self, f"_cmd_{command.replace('-', '_')}", None)
        if handler is not None:
            await handler(args, output)
        else:
            output.append_line(f"[red]Unknown command: /{command}[/red]")

    async def _cmd_help(self, args: str, output: OutputPanel) -> None:
        """Handle /help command."""
        help_text = self._command_parser.get_help_text()
        output.append_line(help_text)

    async def _cmd_new(self, args: str, output: OutputPanel) -> None:
        """Handle /new command."""
        session = self._session_manager.create_session("Session")
        if session:
            output.append_line(
                f"[green]Created new session: {session.name}[/green]",
            )
        else:
            output.append_line("[red]Failed to create session.[/red]")

    async def _cmd_list(self, args: str, output: OutputPanel) -> None:
        """Handle /list command."""
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

    async def _cmd_clear(self, args: str, output: OutputPanel) -> None:
        """Handle /clear command."""
        output.clear_output()
        self._chat_interface.clear()
        output.append_line("[dim]Output cleared.[/dim]")

    async def _cmd_settings(self, args: str, output: OutputPanel) -> None:
        """Handle /settings command."""
        self.app.push_screen(SettingsScreen())

    async def _cmd_quit(self, args: str, output: OutputPanel) -> None:
        """Handle /quit command."""
        output.append_line("[yellow]Goodbye![/yellow]")
        self.app.exit()

    async def _cmd_agents(self, args: str, output: OutputPanel) -> None:
        """Handle /agents command."""
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

    async def _cmd_agent(self, args: str, output: OutputPanel) -> None:
        """Handle /agent command."""
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
                    output.append_line(
                        f"[green]Switched to agent: {target.name}[/green]"
                    )
                    self._update_status_bar()
                else:
                    output.append_line("[red]Failed to create agent instance.[/red]")
            else:
                output.append_line("[red]Failed to switch agent.[/red]")
        else:
            output.append_line(f"[red]Agent '{args}' not found.[/red]")

    async def _cmd_agent_create(self, args: str, output: OutputPanel) -> None:
        """Handle /agent-create command."""
        if not args:
            output.append_line(
                "[yellow]Usage: /agent-create <name> [--model gpt-5-nano] [--provider openai] [--base-url URL] [--api-key KEY] [--system-prompt PROMPT] [--instructions TEXT] [--temperature 1.0] [--max-turns N][/yellow]"
            )
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

    async def _cmd_tools(self, args: str, output: OutputPanel) -> None:
        """Handle /tools command."""
        tools = self._tool_manager.list_tools()
        if tools:
            lines = ["[bold]Available tools:[/bold]"]
            for tool in tools:
                toolset = f" ({tool.toolset})" if tool.toolset else ""
                lines.append(f"  {tool.name}{toolset}")
            output.append_line("\n".join(lines))
        else:
            output.append_line("No tools available.")

    async def _cmd_skills(self, args: str, output: OutputPanel) -> None:
        """Handle /skills command."""
        skills = self._skills_manager.list_skills()
        if skills:
            lines = ["[bold]Available skills:[/bold]"]
            for skill in skills:
                lines.append(f"  {skill.name} - {skill.description}")
            output.append_line("\n".join(lines))
        else:
            output.append_line("No skills available.")

    async def _cmd_reload_skills(self, args: str, output: OutputPanel) -> None:
        """Handle /reload-skills command."""
        if self._skills_manager.reload_skills():
            output.append_line("[green]Skills reloaded successfully.[/green]")
        else:
            output.append_line("[red]Failed to reload skills.[/red]")

    async def _cmd_connect(self, args: str, output: OutputPanel) -> None:
        """Handle /connect command."""
        if not args:
            output.append_line(
                "[yellow]Usage: /connect <backend_url> [--api-key KEY][/yellow]"
            )
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
            output.append_line(
                f"[green]Initialized remote connection to {backend_url}[/green]"
            )
            output.append_line("[dim]Use /sync to sync with backend[/dim]")
        except Exception as e:
            output.append_line(
                f"[red]Failed to initialize remote connection: {e}[/red]"
            )

    async def _cmd_sync(self, args: str, output: OutputPanel) -> None:
        """Handle /sync command."""
        if not self._remote_manager:
            output.append_line("[red]Remote not initialized. Use /connect first.[/red]")
            return
        if not self._remote_manager.is_connected:
            output.append_line(
                "[red]Not connected to remote. Use /connect first.[/red]"
            )
            return
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(self._sync_engine.push_all())
            if result.success:
                output.append_line(
                    f"[green]Sync successful: {result.items_synced} items synced[/green]"
                )
            else:
                output.append_line(f"[red]Sync failed: {result.errors}[/red]")
        except Exception as e:
            output.append_line(f"[red]Sync error: {e}[/red]")

    async def _cmd_export(self, args: str, output: OutputPanel) -> None:
        """Handle the /export command."""
        if not args:
            self.app.push_screen(
                ExportScreen(
                    session_manager=self._session_manager,
                    agent_manager=self._agent_manager,
                    memory_store=self.app.get_memory_store(),
                    skills_manager=self._skills_manager,
                )
            )
            return

        include_sessions = True
        include_agents = True
        include_memory = True
        include_skills = True
        export_format = "json"
        output_path_str = ""

        parts = args.split()
        i = 0
        while i < len(parts):
            part = parts[i]
            if part == "--no-sessions":
                include_sessions = False
                i += 1
            elif part == "--no-agents":
                include_agents = False
                i += 1
            elif part == "--no-memory":
                include_memory = False
                i += 1
            elif part == "--no-skills":
                include_skills = False
                i += 1
            elif part == "--format" and i + 1 < len(parts):
                fmt = parts[i + 1].lower()
                if fmt in ("json", "zip"):
                    export_format = fmt
                else:
                    output.append_line(
                        f"[yellow]Unknown format '{fmt}', using json[/yellow]"
                    )
                i += 2
            elif not output_path_str:
                output_path_str = part
                i += 1
            else:
                i += 1

        if not output_path_str:
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            ext = "zip" if export_format == "zip" else "json"
            output_path_str = str(
                Path.home() / ".tinycua" / f"export-{timestamp}.{ext}"
            )

        output_path = Path(output_path_str)
        valid, error = _validate_path(output_path)
        if not valid:
            output.append_line(f"[red]Invalid export path: {error}[/red]")
            return

        memory_store = self.app.get_memory_store()
        options = ExportOptions(
            include_sessions=include_sessions,
            include_agents=include_agents,
            include_memory=include_memory,
            include_skills=include_skills,
        )

        self.app.push_screen(
            ExportPreviewScreen(
                session_store=self.app.get_session_store(),
                agent_manager=self._agent_manager,
                memory_store=memory_store,
                skills_manager=self._skills_manager,
                options=options,
                output_path=output_path,
                export_format=export_format,
            )
        )

    async def _cmd_import(self, args: str, output: OutputPanel) -> None:
        """Handle the /import command."""
        if not args:
            self.app.push_screen(
                ImportScreen(
                    session_manager=self._session_manager,
                    agent_manager=self._agent_manager,
                    memory_store=self.app.get_memory_store(),
                    skills_manager=self._skills_manager,
                )
            )
            return

        parts = args.split()
        input_path = Path(parts[0])
        valid, error = _validate_path(input_path, must_exist=True)
        if not valid:
            output.append_line(f"[red]Invalid import path: {error}[/red]")
            return

        mode = ImportMode.MERGE

        i = 1
        while i < len(parts):
            if parts[i] == "--mode" and i + 1 < len(parts):
                mode_str = parts[i + 1].lower()
                if mode_str == "replace":
                    output.append_line(
                        "[red]Replace mode is not allowed via CLI. "
                        "Use the Import screen for destructive operations.[/red]"
                    )
                    return
                elif mode_str != "merge":
                    output.append_line(
                        f"[yellow]Unknown mode '{mode_str}', using merge[/yellow]"
                    )
                i += 2
            else:
                i += 1

        try:
            session_store = self.app.get_session_store()
            memory_store = self.app.get_memory_store()
            import_mgr = ImportManager(
                session_store=session_store,
                agent_manager=self._agent_manager,
                memory_store=memory_store,
                skills_manager=self._skills_manager,
            )
            validation = import_mgr.validate(input_path)
            if not validation.valid:
                output.append_line(
                    f"[red]Import validation failed: {'; '.join(validation.errors)}[/red]"
                )
                return

            result = import_mgr.import_data(
                input_path,
                mode=mode,
                progress_callback=lambda msg: output.append_line(f"[dim]{msg}[/dim]"),
            )
            if result.success:
                output.append_line(
                    f"[green]Imported {result.items_imported} items[/green]"
                )
                if result.warnings:
                    for warning in result.warnings:
                        output.append_line(f"[yellow]Warning: {warning}[/yellow]")
            else:
                output.append_line(f"[red]Import failed: {result.error}[/red]")
        except Exception as e:
            output.append_line(f"[red]Import error: {e}[/red]")

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


class FileBrowserScreen(Screen):
    """Simple file browser dialog using DirectoryTree."""

    CSS = """
    FileBrowserScreen {
        align: center middle;
    }
    #file-browser-container {
        width: 80;
        height: 40;
        border: solid $primary;
        padding: 1;
    }
    #file-browser-path {
        height: 3;
        content-align: left middle;
        background: $surface-darken-1;
        color: $text;
        padding: 0 1;
    }
    #file-browser-buttons {
        layout: horizontal;
        height: auto;
        margin: 1 0 0 0;
    }
    """

    def __init__(
        self,
        initial_path: Path | None = None,
        on_select: Callable[[Path], None] | None = None,
        select_file: bool = True,
    ) -> None:
        """Initialize the file browser screen.

        Args:
            initial_path: Starting directory.
            on_select: Callback receiving the selected Path.
            select_file: If True, only files can be selected.
        """
        super().__init__()
        self._initial_path = initial_path or Path.home()
        self._on_select = on_select
        self._select_file = select_file
        self._current_path = self._initial_path

    def compose(self) -> ComposeResult:
        """Compose the file browser layout."""
        yield Container(
            Static(
                f"Current: {self._current_path}",
                id="file-browser-path",
            ),
            DirectoryTree(self._initial_path, id="file-browser-tree"),
            Container(
                Button("Cancel", id="btn-cancel", variant="error"),
                Button("Select", id="btn-select", variant="success"),
                id="file-browser-buttons",
            ),
            id="file-browser-container",
        )

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """Handle directory selection."""
        self._current_path = event.path
        path_label = self.query_one("#file-browser-path", Static)
        path_label.update(f"Current: {self._current_path}")

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Handle file selection."""
        self._current_path = event.path
        path_label = self.query_one("#file-browser-path", Static)
        path_label.update(f"Current: {self._current_path}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-cancel":
            self.app.pop_screen()
        elif event.button.id == "btn-select":
            if self._select_file and self._current_path.is_dir():
                self.app.notify("Please select a file", severity="warning")
                return
            if self._on_select:
                self._on_select(self._current_path)
            self.app.pop_screen()


class ConfirmScreen(Screen):
    """Confirmation dialog screen."""

    CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #confirm-container {
        width: 50;
        height: auto;
        border: solid $primary;
        padding: 2;
    }
    """

    def __init__(self, message: str, on_confirm: Callable[[], None]) -> None:
        """Initialize the confirmation screen."""
        super().__init__()
        self._message = message
        self._on_confirm = on_confirm

    def compose(self) -> ComposeResult:
        """Compose the confirmation screen layout."""
        yield Container(
            Static(self._message, id="confirm-message"),
            Container(
                Button("No", id="btn-no", variant="error"),
                Button("Yes", id="btn-yes", variant="success"),
                id="confirm-buttons",
            ),
            id="confirm-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-yes":
            self._on_confirm()
        self.app.pop_screen()


class ExportPreviewScreen(Screen):
    """Preview export contents before executing."""

    CSS = """
    ExportPreviewScreen {
        align: center middle;
    }
    #preview-container {
        width: 60;
        height: auto;
        border: solid $primary;
        padding: 2;
    }
    #preview-content {
        height: auto;
        margin: 1 0;
    }
    """

    def __init__(
        self,
        session_store: LocalSessionStore,
        agent_manager: AgentManager,
        memory_store: LocalMemoryStore,
        skills_manager: SkillsManager,
        options: Any,
        output_path: Path,
        export_format: str = "json",
    ) -> None:
        """Initialize the preview screen."""
        super().__init__()
        self._session_store = session_store
        self._agent_manager = agent_manager
        self._memory_store = memory_store
        self._skills_manager = skills_manager
        self._options = options
        self._output_path = output_path
        self._export_format = export_format

    def compose(self) -> ComposeResult:
        """Compose the preview screen layout."""
        lines = ["[bold]Export Preview[/bold]", ""]
        lines.append(f"  Format: {self._export_format.upper()}")

        if self._options.include_sessions:
            count = len(self._session_store.list_sessions())
            lines.append(f"  Sessions: {count}")
        if self._options.include_agents:
            count = len(self._agent_manager.list_agents())
            lines.append(f"  Agents: {count}")
        if self._options.include_memory:
            count = len(self._memory_store.list_keys())
            lines.append(f"  Memory keys: {count}")
        if self._options.include_skills:
            count = len(self._skills_manager.list_skills())
            lines.append(f"  Skills: {count}")

        lines.append(f"\nOutput path: {self._output_path}")

        if self._output_path.exists():
            lines.append(
                "\n[yellow]Warning: File already exists. "
                "Overwrite, rename, or cancel?[/yellow]"
            )
            buttons = [
                Button("Cancel", id="btn-cancel", variant="error"),
                Button("Rename", id="btn-rename", variant="warning"),
                Button("Overwrite", id="btn-overwrite", variant="primary"),
            ]
        else:
            buttons = [
                Button("Cancel", id="btn-cancel", variant="error"),
                Button("Export", id="btn-export", variant="success"),
            ]

        yield Container(
            Static("\n".join(lines), id="preview-content"),
            Container(*buttons, id="preview-buttons"),
            id="preview-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        if button_id == "btn-cancel":
            self.app.pop_screen()
        elif button_id == "btn-export":
            self._run_export()
        elif button_id == "btn-overwrite":
            self._run_export(overwrite=True)
        elif button_id == "btn-rename":
            self._run_export(rename=True)

    def _run_export(self, overwrite: bool = False, rename: bool = False) -> None:
        """Execute the export."""
        output_path = self._output_path

        if rename and output_path.exists():
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            stem = output_path.stem
            suffix = output_path.suffix
            candidate = output_path.with_name(f"{stem}-{timestamp}{suffix}")
            if candidate.exists():
                self.app.notify(
                    "Export cancelled: renamed file also exists",
                    severity="warning",
                )
                self.app.pop_screen()
                return
            output_path = candidate
        elif output_path.exists() and not overwrite:
            self.app.notify(
                "Export cancelled: file exists",
                severity="warning",
            )
            self.app.pop_screen()
            return

        try:
            export_mgr = ExportManager(
                session_store=self._session_store,
                agent_manager=self._agent_manager,
                memory_store=self._memory_store,
                skills_manager=self._skills_manager,
            )
            if self._export_format == "zip":
                result = export_mgr.export_zip(output_path, self._options)
            else:
                result = export_mgr.export(output_path, self._options)
            if result.success:
                self.app.notify(
                    f"Exported {result.items_exported} items to {result.output_path}",
                    severity="information",
                )
            else:
                self.app.notify(f"Export failed: {result.error}", severity="error")
        except Exception as e:
            self.app.notify(f"Export error: {e}", severity="error")

        self.app.pop_screen()


class ExportScreen(Screen):
    """Export data screen with granular item selection."""

    CSS = """
    ExportScreen {
        align: center middle;
    }
    #export-container {
        width: 80;
        height: auto;
        border: solid $primary;
        padding: 2;
    }
    .export-row {
        layout: horizontal;
        height: auto;
        margin: 1 0;
    }
    .export-label {
        width: 20;
    }
    #export-output {
        width: 1fr;
    }
    #export-granular {
        height: auto;
        margin: 1 0;
    }
    .export-granular-title {
        text-style: bold;
        margin: 1 0 0 0;
    }
    """

    def __init__(
        self,
        session_manager: TuiSessionManager,
        agent_manager: AgentManager,
        memory_store: LocalMemoryStore,
        skills_manager: SkillsManager,
    ) -> None:
        """Initialize the export screen."""
        super().__init__()
        self._session_manager = session_manager
        self._agent_manager = agent_manager
        self._memory_store = memory_store
        self._skills_manager = skills_manager

    def compose(self) -> ComposeResult:
        """Compose the export screen layout."""
        yield Container(
            Static("[bold]Export Data[/bold]", id="title"),
            Container(
                Label("Select data to export:", classes="export-label"),
                Checkbox("Sessions", id="chk-sessions", value=True),
                Checkbox("Agents", id="chk-agents", value=True),
                Checkbox("Memory", id="chk-memory", value=True),
                Checkbox("Skills", id="chk-skills", value=True),
                id="export-options",
            ),
            Container(
                Static("Specific sessions:", classes="export-granular-title"),
                SelectionList(id="sel-sessions"),
                Static("Specific agents:", classes="export-granular-title"),
                SelectionList(id="sel-agents"),
                id="export-granular",
            ),
            Container(
                Label("Format:", classes="export-label"),
                RadioSet(
                    RadioButton("JSON", id="rad-json", value=True),
                    RadioButton("ZIP", id="rad-zip"),
                    id="export-format",
                ),
                id="export-format-row",
            ),
            Container(
                Label("Output:", classes="export-label"),
                Input(
                    placeholder="Export path...",
                    id="export-output",
                ),
                Button("Browse", id="btn-browse", variant="primary"),
                id="export-path-row",
            ),
            Container(
                Button("Cancel", id="btn-cancel", variant="error"),
                Button("Export", id="btn-export", variant="success"),
                id="export-buttons",
            ),
            id="export-container",
        )

    def on_mount(self) -> None:
        """Handle screen mount."""
        default_path = str(
            Path.home()
            / ".tinycua"
            / f"export-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )
        self.query_one("#export-output", Input).value = default_path

        sessions = self._session_manager.list_sessions()
        agents = self._agent_manager.list_agents()
        memory_keys = self._memory_store.list_keys()
        skills = self._skills_manager.list_skills()

        self.query_one("#chk-sessions", Checkbox).label = f"Sessions ({len(sessions)})"
        self.query_one("#chk-agents", Checkbox).label = f"Agents ({len(agents)})"
        self.query_one("#chk-memory", Checkbox).label = f"Memory ({len(memory_keys)})"
        self.query_one("#chk-skills", Checkbox).label = f"Skills ({len(skills)})"

        session_list = self.query_one("#sel-sessions", SelectionList)
        for session in sessions:
            session_list.add_option(
                (session.name, str(session.id)),
            )

        agent_list = self.query_one("#sel-agents", SelectionList)
        for agent in agents:
            agent_list.add_option(
                (agent.name, str(agent.id)),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        if button_id == "btn-cancel":
            self.app.pop_screen()
        elif button_id == "btn-browse":
            self._browse_output()
        elif button_id == "btn-export":
            self._do_export()

    def _browse_output(self) -> None:
        """Open file browser to choose export directory."""
        current = Path(self.query_one("#export-output", Input).value or ".").parent

        def on_select(selected_path: Path) -> None:
            if selected_path.is_dir():
                filename = (
                    Path(self.query_one("#export-output", Input).value).name
                    or f"export-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
                )
                self.query_one("#export-output", Input).value = str(
                    selected_path / filename
                )
            else:
                self.query_one("#export-output", Input).value = str(selected_path)

        self.app.push_screen(
            FileBrowserScreen(
                initial_path=current,
                on_select=on_select,
                select_file=False,
            )
        )

    def _do_export(self) -> None:
        """Show export preview before performing export."""
        output_path = Path(self.query_one("#export-output", Input).value)
        valid, error = _validate_path(output_path)
        if not valid:
            self.app.notify(f"Invalid path: {error}", severity="error")
            return

        include_sessions = self.query_one("#chk-sessions", Checkbox).value
        include_agents = self.query_one("#chk-agents", Checkbox).value
        include_memory = self.query_one("#chk-memory", Checkbox).value
        include_skills = self.query_one("#chk-skills", Checkbox).value

        session_list = self.query_one("#sel-sessions", SelectionList)
        selected_sessions = (
            list(session_list.selected) if session_list.selected else None
        )

        agent_list = self.query_one("#sel-agents", SelectionList)
        selected_agents = list(agent_list.selected) if agent_list.selected else None

        format_radio = self.query_one("#export-format", RadioSet)
        pressed = format_radio.pressed_button
        export_format = (
            "zip" if pressed is not None and pressed.id == "rad-zip" else "json"
        )

        options = ExportOptions(
            include_sessions=include_sessions,
            include_agents=include_agents,
            include_memory=include_memory,
            include_skills=include_skills,
            session_ids=selected_sessions,
            agent_ids=selected_agents,
        )

        self.app.push_screen(
            ExportPreviewScreen(
                session_store=self.app.get_session_store(),
                agent_manager=self._agent_manager,
                memory_store=self._memory_store,
                skills_manager=self._skills_manager,
                options=options,
                output_path=output_path,
                export_format=export_format,
            )
        )


class ImportScreen(Screen):
    """Import data screen."""

    CSS = """
    ImportScreen {
        align: center middle;
    }
    #import-container {
        width: 60;
        height: auto;
        border: solid $primary;
        padding: 2;
    }
    .import-row {
        layout: horizontal;
        height: auto;
        margin: 1 0;
    }
    .import-label {
        width: 20;
    }
    #import-path {
        width: 1fr;
    }
    #import-preview {
        height: 8;
        border: solid $primary-darken-2;
        padding: 1;
    }
    """

    def __init__(
        self,
        session_manager: TuiSessionManager,
        agent_manager: AgentManager,
        memory_store: LocalMemoryStore,
        skills_manager: SkillsManager,
    ) -> None:
        """Initialize the import screen."""
        super().__init__()
        self._session_manager = session_manager
        self._agent_manager = agent_manager
        self._memory_store = memory_store
        self._skills_manager = skills_manager

    def compose(self) -> ComposeResult:
        """Compose the import screen layout."""
        yield Container(
            Static("[bold]Import Data[/bold]", id="title"),
            Container(
                Label("File:", classes="import-label"),
                Input(
                    placeholder="Path to import file...",
                    id="import-path",
                ),
                Button("Browse", id="btn-browse", variant="primary"),
                id="import-path-row",
            ),
            Static("Preview:\nSelect a file to see preview.", id="import-preview"),
            Container(
                Label("Mode:", classes="import-label"),
                RadioSet(
                    RadioButton("Merge (add to existing)", id="rad-merge", value=True),
                    RadioButton("Replace (replace all)", id="rad-replace"),
                    id="import-mode",
                ),
                id="import-mode-row",
            ),
            Container(
                Button("Cancel", id="btn-cancel", variant="error"),
                Button("Import", id="btn-import", variant="success"),
                id="import-buttons",
            ),
            id="import-container",
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Update preview when file path changes."""
        if event.input.id == "import-path":
            self._update_preview(event.value)

    def _update_preview(self, path_str: str) -> None:
        """Update the import preview."""
        preview = self.query_one("#import-preview", Static)
        path = Path(path_str)
        valid, error = _validate_path(path, must_exist=True)
        if not valid:
            preview.update(f"Preview:\n{error}")
            return

        try:
            session_store = self.app.get_session_store()
            import_mgr = ImportManager(
                session_store=session_store,
                agent_manager=self._agent_manager,
                memory_store=self._memory_store,
                skills_manager=self._skills_manager,
            )
            validation = import_mgr.validate(path)
            if validation.valid:
                lines = [
                    "Preview:",
                    f"  Version: {validation.version}",
                    f"  Data types: {', '.join(validation.data_types)}",
                ]
                if validation.warnings:
                    lines.append("  Warnings:")
                    for warning in validation.warnings:
                        lines.append(f"    - {warning}")
                preview.update("\n".join(lines))
            else:
                lines = ["Preview:", "Validation failed:"]
                for error in validation.errors:
                    lines.append(f"  - {error}")
                preview.update("\n".join(lines))
        except Exception as e:
            preview.update(f"Preview:\nError: {e}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        if button_id == "btn-cancel":
            self.app.pop_screen()
        elif button_id == "btn-browse":
            self._browse_file()
        elif button_id == "btn-import":
            self._do_import()

    def _browse_file(self) -> None:
        """Open file browser to select import file."""
        current = Path(self.query_one("#import-path", Input).value or ".").parent

        def on_select(selected_path: Path) -> None:
            self.query_one("#import-path", Input).value = str(selected_path)

        self.app.push_screen(
            FileBrowserScreen(
                initial_path=current,
                on_select=on_select,
                select_file=True,
            )
        )

    def _do_import(self) -> None:
        """Perform the import."""
        path = Path(self.query_one("#import-path", Input).value)
        valid, error = _validate_path(path, must_exist=True)
        if not valid:
            self.app.notify(f"Invalid path: {error}", severity="error")
            return

        radio_set = self.query_one("#import-mode", RadioSet)
        pressed = radio_set.pressed_button
        mode = (
            ImportMode.REPLACE
            if pressed is not None and pressed.id == "rad-replace"
            else ImportMode.MERGE
        )

        if mode == ImportMode.REPLACE:
            self.app.push_screen(
                ConfirmScreen(
                    "This will delete ALL existing data. Are you sure?",
                    on_confirm=lambda: self._run_import(path, mode),
                )
            )
            return

        self._run_import(path, mode)

    def _run_import(self, path: Path, mode: ImportMode) -> None:
        """Execute the import after confirmation.

        Args:
            path: Path to the import file.
            mode: Import mode (MERGE or REPLACE).
        """
        try:
            session_store = self.app.get_session_store()
            import_mgr = ImportManager(
                session_store=session_store,
                agent_manager=self._agent_manager,
                memory_store=self._memory_store,
                skills_manager=self._skills_manager,
            )
            validation = import_mgr.validate(path)
            if not validation.valid:
                self.app.notify(
                    f"Import validation failed: {'; '.join(validation.errors)}",
                    severity="error",
                )
                return

            result = import_mgr.import_data(
                path,
                mode=mode,
                progress_callback=lambda msg: self.app.notify(
                    msg, severity="information"
                ),
            )
            if result.success:
                self.app.notify(
                    f"Imported {result.items_imported} items",
                    severity="information",
                )
                if result.warnings:
                    for warning in result.warnings:
                        self.app.notify(f"Warning: {warning}", severity="warning")
            else:
                self.app.notify(f"Import failed: {result.error}", severity="error")
        except Exception as e:
            self.app.notify(f"Import error: {e}", severity="error")

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
        self._local_memory_store: LocalMemoryStore | None = None
        self._local_session_store: LocalSessionStore | None = None

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
        logger.info("Initialized remote manager for %s", backend_url)

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

    def get_memory_store(self) -> LocalMemoryStore:
        """Get the shared local memory store."""
        if self._local_memory_store is None:
            self._local_memory_store = LocalMemoryStore(
                str(self._storage_manager.db_path)
            )
        return self._local_memory_store

    def get_session_store(self) -> LocalSessionStore:
        """Get the shared local session store."""
        if self._local_session_store is None:
            self._local_session_store = LocalSessionStore(
                self._storage_manager.get_store()
            )
        return self._local_session_store

    def get_command_parser(self) -> CommandParser:
        """Get the command parser."""
        return self._command_parser
