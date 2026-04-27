"""Async CLI command handlers for tinycua."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rich.console import Console

console = Console()


async def cmd_run(args: argparse.Namespace) -> int:
    """Run agent with input string or script file.

    If args.input is provided, treat as direct input string.
    If args.file is provided, read and execute the script file.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        from tinycua.agent.default_agent import create_default_agent

        agent = create_default_agent()

        if hasattr(args, "file") and args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                console.print(f"[red]Error: File not found: {file_path}[/red]")
                return 1
            user_input = file_path.read_text()
        elif hasattr(args, "input") and args.input:
            user_input = args.input
        else:
            console.print("[red]Error: Provide input string or --file path[/red]")
            return 1

        console.print(f"[dim]Running agent with input: {user_input[:100]}...[/dim]")
        result = await agent.run(user_input)
        console.print(f"[green]{result}[/green]")
        return 0

    except (OSError, ValueError, TypeError) as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


async def cmd_deploy(args: argparse.Namespace) -> int:
    """Deploy agent and tools to backend.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        from tinycua.agent.default_agent import create_default_agent
        from tinycua.agent.lifecycle import AgentLifecycle

        # Check if file argument is provided
        file_path = getattr(args, "file", None)
        if file_path:
            console.print(
                "[yellow]Note: Loading agent from file is not yet implemented. Using default agent.[/yellow]"
            )

        agent = create_default_agent()

        backend_url = getattr(args, "backend_url", None)
        api_key = getattr(args, "api_key", None)

        lifecycle = AgentLifecycle(
            agent,
            backend_url=backend_url,
            backend_api_key=api_key,
        )

        console.print("[dim]Deploying agent to backend...[/dim]")
        result = await lifecycle.deploy()

        console.print("[green]Deployed successfully![/green]")
        console.print(f"  Agent ID: {result.get('id', 'unknown')}")
        console.print(f"  Status: {result.get('status', 'unknown')}")
        return 0

    except (OSError, ValueError, TypeError) as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


async def cmd_chat(args: argparse.Namespace) -> int:
    """Start interactive chat session.

    This is a thin wrapper that enters a chat loop using the same
    shared chat logic as the REPL /chat command.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        from tinycua.agent.default_agent import create_default_agent

        agent = create_default_agent()

        console.print("[bold green]TinyCUA Chat[/bold green]")
        console.print("Type 'quit' or 'exit' to leave\n")

        while True:
            try:
                user_input = await asyncio.to_thread(
                    console.input, "[bold blue]You>[/bold blue] "
                )
                user_input = user_input.strip()

                if user_input.lower() in ("quit", "exit"):
                    console.print("[yellow]Goodbye![/yellow]")
                    break

                if not user_input:
                    continue

                console.print("[dim]Thinking...[/dim]")
                result = await agent.run(user_input)
                console.print(f"[green]Assistant: {result}[/green]\n")

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'quit' to exit[/yellow]")
            except EOFError:
                break

        return 0

    except (OSError, ValueError, TypeError) as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


async def cmd_tui(args: argparse.Namespace) -> int:
    """Launch Textual TUI application.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        from tinycua.tui.app import TinyCUAApp

        app = TinyCUAApp()
        await app.run_async()
        return 0

    except ImportError:
        console.print(
            "[red]Error: Textual is not installed. "
            "Install with: pip install tinycua[tui][/red]"
        )
        return 1
    except (OSError, ValueError, TypeError) as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
