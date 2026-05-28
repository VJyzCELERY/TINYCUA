"""Interactive REPL."""

from rich.console import Console

console = Console()


def run_repl() -> int:
    """Run the interactive REPL."""
    console.print("[bold green]Welcome to TINYCUA SDK REPL[/bold green]")
    console.print("Type /help for available commands\n")

    while True:
        try:
            user_input = console.input("[bold blue]>[/bold blue] ")
            if user_input.strip() == "/quit":
                console.print("[yellow]Goodbye![/yellow]")
                break
            elif user_input.strip() == "/help":
                _print_help()
            elif user_input.strip():
                console.print(f"[dim]Echo: {user_input}[/dim]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Use /quit to exit[/yellow]")
        except EOFError:
            break

    return 0


def _print_help() -> None:
    """Print available commands."""
    console.print("""
[bold]Available commands:[/bold]
  /help              Show this help message
  /connect <url>     Connect to backend
  /status            Show connection status
  /agents            List available agents
  /run <file>        Run a script
  /chat <agent>      Start chat with agent
  /deploy <file>    Deploy tools
  /quit              Exit REPL
""")


__all__ = ["run_repl"]
