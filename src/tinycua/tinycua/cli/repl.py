"""Interactive REPL for TINYCUA agent interaction with prompt-toolkit."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from rich.console import Console

console = Console()

SLASH_COMMANDS = [
    "/connect",
    "/status",
    "/agents",
    "/chat",
    "/run",
    "/deploy",
    "/help",
    "/quit",
    "/clear",
    "/history",
]


class REPLCommandHandler:
    """Handles all REPL slash commands.

    Manages backend connections, agent interactions, and command execution
    within the REPL session.
    """

    def __init__(self) -> None:
        """Initialize the REPL command handler."""
        self._backend_url: str | None = None
        self._backend_client: Any = None
        self._connected: bool = False
        self._chat_history: list[dict[str, str]] = []

    async def handle_connect(self, url: str) -> str:
        """Connect to a backend server.

        Args:
            url: Backend server URL.

        Returns:
            Status message.
        """
        self._backend_url = url
        try:
            from tinycua.clients.backend import BackendClient

            self._backend_client = BackendClient(base_url=url)
            healthy = await self._backend_client.health_check()
            self._connected = healthy
            if healthy:
                return f"[green]Connected to {url}[/green]"
            return f"[yellow]Connected to {url} but health check failed[/yellow]"
        except Exception as e:
            self._connected = False
            return f"[red]Failed to connect to {url}: {e}[/red]"

    async def handle_status(self) -> str:
        """Show connection and agent status.

        Returns:
            Status message.
        """
        status_lines = []
        status_lines.append(f"Backend: {self._backend_url or 'Not connected'}")
        status_lines.append(f"Connected: {'Yes' if self._connected else 'No'}")
        status_lines.append(f"Chat history: {len(self._chat_history)} turns")
        return "\n".join(status_lines)

    async def handle_agents(self) -> str:
        """List available agents on backend.

        Returns:
            List of agents or status message.
        """
        if not self._connected or not self._backend_client:
            return "[yellow]Not connected to a backend. Use /connect first.[/yellow]"

        try:
            agents = await self._backend_client.list_agents()
            if not agents:
                return "No agents found on backend."
            lines = ["Available agents:"]
            for agent in agents:
                name = agent.get("name", "unknown")
                lines.append(f"  - {name}")
            return "\n".join(lines)
        except Exception as e:
            return f"[red]Failed to list agents: {e}[/red]"

    async def handle_chat(self, agent_name: str) -> str:
        """Start chat with specified agent.

        Args:
            agent_name: Name of the agent to chat with.

        Returns:
            Chat session started message.
        """
        try:
            from tinycua.agent.default_agent import create_default_agent

            agent = create_default_agent()
            chat_name = agent_name or "assistant"
            agent.config.name = chat_name

            console.print(f"[bold green]Chatting with {chat_name}[/bold green]")
            console.print("Type 'back' to return to REPL\n")

            while True:
                try:
                    user_input = console.input("[bold blue]You>[/bold blue] ")
                    user_input = user_input.strip()

                    if user_input.lower() in ("back", "quit", "exit"):
                        console.print("[yellow]Returning to REPL...[/yellow]")
                        break

                    if not user_input:
                        continue

                    console.print("[dim]Thinking...[/dim]")
                    result = await agent.run(user_input)
                    self._chat_history.append({"role": "user", "content": user_input})
                    self._chat_history.append({"role": "assistant", "content": result})
                    console.print(f"[green]Assistant: {result}[/green]\n")

                except KeyboardInterrupt:
                    console.print("\n[yellow]Use 'back' to return[/yellow]")
                except EOFError:
                    break

            return "Chat session ended."

        except Exception as e:
            return f"[red]Chat error: {e}[/red]"

    async def handle_run(self, file_path: str) -> str:
        """Run a script file.

        Args:
            file_path: Path to the script file.

        Returns:
            Execution result or error message.
        """
        try:
            from pathlib import Path as PathLib

            path = PathLib(file_path)
            if not path.exists():
                return f"[red]File not found: {file_path}[/red]"

            content = path.read_text()
            from tinycua.agent.default_agent import create_default_agent

            agent = create_default_agent()
            result = await agent.run(content)
            return f"[green]Result: {result}[/green]"

        except Exception as e:
            return f"[red]Run error: {e}[/red]"

    async def handle_deploy(self, file_path: str) -> str:
        """Deploy tools from file.

        Args:
            file_path: Path to the agent definition file.

        Returns:
            Deployment result or error message.
        """
        try:
            from pathlib import Path as PathLib

            from tinycua.agent.default_agent import create_default_agent
            from tinycua.agent.lifecycle import AgentLifecycle

            # Validate file exists if provided
            if file_path:
                path = PathLib(file_path)
                if not path.exists():
                    return f"[red]File not found: {file_path}[/red]"
                # Note: Loading agent from file is not yet implemented
                console.print(
                    "[yellow]Note: Loading agent from file is not yet implemented. Using default agent.[/yellow]"
                )

            agent = create_default_agent()
            lifecycle = AgentLifecycle(agent, backend_url=self._backend_url)

            result = await lifecycle.deploy()
            return f"[green]Deployed! Agent ID: {result.get('id', 'unknown')}[/green]"

        except Exception as e:
            return f"[red]Deploy error: {e}[/red]"

    def handle_help(self) -> str:
        """Show available commands.

        Returns:
            Help text.
        """
        return """[bold]Available commands:[/bold]
  /connect <url>     Connect to backend server
  /status            Show connection and agent status
  /agents            List available agents on backend
  /chat <agent>      Start chat with specified agent
  /run <file>        Run a script file
  /deploy <file>     Deploy tools from file
  /help              Show this help message
  /quit              Exit REPL
  /clear             Clear the screen
  /history           Show chat history"""

    def handle_quit(self) -> None:
        """Exit the REPL."""
        console.print("[yellow]Goodbye![/yellow]")

    def handle_clear(self) -> None:
        """Clear the console screen."""
        console.clear()

    def handle_history(self) -> str:
        """Show chat history.

        Returns:
            Chat history or message.
        """
        if not self._chat_history:
            return "No chat history yet."

        lines = ["[bold]Chat History:[/bold]"]
        for entry in self._chat_history:
            role = entry.get("role", "unknown")
            content = entry.get("content", "")
            prefix = "You" if role == "user" else "Assistant"
            lines.append(f"[blue]{prefix}>[/blue] {content[:200]}")
        return "\n".join(lines)


def _get_history_path() -> Path:
    """Get the path to the REPL history file.

    Returns:
        Path to the history file in ~/.tinycua/.
    """
    history_dir = Path.home() / ".tinycua"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir / "repl_history"


def run_repl() -> int:
    """Run the interactive REPL with full command support.

    Uses prompt-toolkit for command history and tab completion.

    Returns:
        Exit code (0 for normal exit).
    """
    history_path = _get_history_path()
    session = PromptSession(
        history=FileHistory(str(history_path)),
        completer=WordCompleter(SLASH_COMMANDS, ignore_case=True),
    )

    handler = REPLCommandHandler()

    console.print("[bold green]Welcome to TINYCUA REPL[/bold green]")
    console.print("Type /help for available commands\n")

    while True:
        try:
            user_input = session.prompt("> ")
            user_input = user_input.strip()

            if not user_input:
                continue

            if user_input.startswith("/"):
                result = asyncio.run(_handle_slash_command(user_input, handler))
                if result is None:
                    break
                if result:
                    console.print(result)
            else:
                console.print(f"[dim]Sending to agent: {user_input}[/dim]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Use /quit to exit[/yellow]")
        except EOFError:
            break

    return 0


async def _handle_slash_command(
    command: str, handler: REPLCommandHandler
) -> str | None:
    """Parse and execute a slash command.

    Args:
        command: The full slash command string.
        handler: The REPLCommandHandler instance.

    Returns:
        Result message to display, or None to exit.
    """
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/quit":
        handler.handle_quit()
        return None
    elif cmd == "/help":
        return handler.handle_help()
    elif cmd == "/clear":
        handler.handle_clear()
        return None
    elif cmd == "/connect":
        if not arg:
            return "[red]Usage: /connect <url>[/red]"
        return await handler.handle_connect(arg)
    elif cmd == "/status":
        return await handler.handle_status()
    elif cmd == "/agents":
        return await handler.handle_agents()
    elif cmd == "/chat":
        if not arg:
            return await handler.handle_chat("assistant")
        return await handler.handle_chat(arg)
    elif cmd == "/run":
        if not arg:
            return "[red]Usage: /run <file>[/red]"
        return await handler.handle_run(arg)
    elif cmd == "/deploy":
        if not arg:
            return "[red]Usage: /deploy <file>[/red]"
        return await handler.handle_deploy(arg)
    elif cmd == "/history":
        return handler.handle_history()
    else:
        return f"[red]Unknown command: {cmd}. Type /help for available commands.[/red]"


__all__ = ["run_repl", "REPLCommandHandler", "SLASH_COMMANDS"]
