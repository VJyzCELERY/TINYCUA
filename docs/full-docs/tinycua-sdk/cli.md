# CLI Documentation

The `cli/` package provides the command-line interface for the TINYCUA SDK.

**Package path:** `tinycua_sdk/cli/`

---

## main.py - CLI Entry Point

### Purpose

Defines the argument parser and dispatches to subcommands.

### main() Function

```python
def main() -> int:
    parser = argparse.ArgumentParser(prog="tinycua", description="TINYCUA SDK CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("repl", help="Start interactive REPL")
    
    run_parser = subparsers.add_parser("run", help="Run a Python script")
    run_parser.add_argument("file", help="Script file to run")
    
    deploy_parser = subparsers.add_parser("deploy", help="Deploy tools")
    deploy_parser.add_argument("file", help="File containing tools to deploy")
    
    agent_parser = subparsers.add_parser("agent", help="Manage agents")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command")
    
    # Agent subcommands...
```

**Commands:**
- `repl`: Start interactive REPL
- `run <file>`: Run a Python script (placeholder)
- `deploy <file>`: Deploy tools (placeholder)
- `agent`: Agent management subcommands

### Agent Subcommands

**create:**
```python
create_parser = agent_subparsers.add_parser("create", help="Create an agent")
create_parser.add_argument("path", nargs="?", help="Path to AGENT.md file or directory")
create_parser.add_argument("--template", help="Template name (coder, researcher, assistant)")
create_parser.add_argument("--model", help="Override model")
create_parser.add_argument("--provider", help="Override provider")
create_parser.add_argument("--tools", help="Override tools (comma-separated)")
create_parser.add_argument("--skills", help="Override skills (comma-separated)")
create_parser.add_argument("--loop", help="Override loop type")
create_parser.add_argument("--temperature", type=float, help="Override temperature")
create_parser.add_argument("--override-file", help="Path to JSON/YAML override file")
```

**templates:**
```python
templates_parser = agent_subparsers.add_parser("templates", help="List available templates")
templates_parser.add_argument("--verbose", action="store_true", help="Show detailed info")
```

**info:**
```python
info_parser = agent_subparsers.add_parser("info", help="Show agent configuration")
info_parser.add_argument("--file", help="Path to AGENT.md")
info_parser.add_argument("--template", help="Template name")
```

### Command Dispatch

```python
if args.command == "repl":
    from tinycua_sdk.cli.repl import run_repl
    return run_repl()

if args.command == "agent":
    from tinycua_sdk.cli.agent_commands import cmd_agent_create, cmd_agent_templates, cmd_agent_info
    
    if args.agent_command == "create":
        return asyncio.run(cmd_agent_create(args))
    if args.agent_command == "templates":
        return asyncio.run(cmd_agent_templates(args))
    if args.agent_command == "info":
        return asyncio.run(cmd_agent_info(args))
```

**Async dispatch:** Agent commands are async functions, so `asyncio.run()` bridges sync CLI entry to async implementations.

---

## repl.py - Interactive REPL

### Purpose

Provides a basic interactive REPL with rich terminal formatting.

### run_repl()

```python
def run_repl() -> int:
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
```

**Commands:**
- `/quit`: Exit REPL
- `/help`: Show help
- Any other input: Echo (placeholder)

**Exception handling:**
- `KeyboardInterrupt` (Ctrl+C): Reminds user to use `/quit`
- `EOFError` (Ctrl+D): Clean exit

**Rich formatting:** Uses `rich.console.Console` for colored output and styled text.

### Available Commands Help

```
/help              Show this help message
/connect <url>     Connect to backend
/status            Show connection status
/agents            List available agents
/run <file>        Run a script
/chat <agent>      Start chat with agent
/deploy <file>     Deploy tools
/quit              Exit REPL
```

Most commands are listed in help but not yet implemented in the basic REPL.

---

## agent_commands.py - Agent CLI Commands

### Purpose

Implements the `agent` subcommands for creating, listing, and inspecting agents.

### Helper Functions

#### _validate_agent_path()

```python
def _validate_agent_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    original_str = str(path)
    if ".." in original_str:
        raise ValueError("Invalid path - directory traversal not allowed")
    return resolved
```

**Security check:** Prevents `..` in paths to stop directory traversal attacks. Note: This is a simple string check and may have false positives (e.g., paths containing `..` as part of a legitimate directory name).

#### _load_override_file()

```python
def _load_override_file(path: Path) -> dict:
    if not path.exists():
        raise ValueError(f"Override file not found: {path}")
    
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"Override file is empty: {path}")
    
    if path.suffix == ".json":
        return json.loads(content)
    elif path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(content) or {}
    else:
        raise ValueError(f"Unsupported override file format. Use .json or .yaml/.yml: {path}")
```

Supports JSON and YAML override files. Validates existence and non-emptiness.

#### _build_cli_overrides()

```python
def _build_cli_overrides(args: argparse.Namespace) -> dict:
    cli_overrides = {}
    if args.model:
        cli_overrides["model"] = args.model
    if args.provider:
        cli_overrides["provider"] = args.provider
    if args.tools:
        cli_overrides["tools"] = [t.strip() for t in args.tools.split(",")]
    if args.skills:
        cli_overrides["skills"] = [s.strip() for s in args.skills.split(",")]
    if args.loop:
        cli_overrides["loop"] = args.loop
    if args.temperature is not None:
        cli_overrides["temperature"] = args.temperature
    return cli_overrides
```

Converts CLI arguments to override dict. Parses comma-separated lists for tools and skills.

### cmd_agent_create()

```python
async def cmd_agent_create(args: argparse.Namespace) -> int:
    if args.path:
        return await _create_from_file(args)
    elif args.template:
        return await _create_from_template(args)
    else:
        console.print("[red]Error: Specify either a path to AGENT.md or --template name[/red]")
        return 1
```

Dispatches to file-based or template-based creation.

#### _create_from_file()

```python
async def _create_from_file(args: argparse.Namespace) -> int:
    agent_path = Path(args.path)
    agent_path = _validate_agent_path(agent_path)
    
    loader = AgentLoader()
    config = loader.load_from_markdown(agent_path)
    
    console.print(
        f"[green]Agent '{config.name}' created successfully![/green]\n"
        f"  Model: {config.model}\n"
        f"  Provider: {config.provider}\n"
        f"  Tools: {len(config.tools)}"
    )
    return 0
```

Loads agent from `AGENT.md` and displays configuration summary.

#### _create_from_template()

```python
async def _create_from_template(args: argparse.Namespace) -> int:
    template = get_template(args.template)
    
    file_overrides = {}
    if args.override_file:
        file_overrides = _load_override_file(Path(args.override_file))
    
    cli_overrides = _build_cli_overrides(args)
    merged_overrides = {**file_overrides, **cli_overrides}  # CLI wins
    
    final_template = apply_template_overrides(template, merged_overrides)
    
    console.print(
        f"[green]Agent '{final_template['name']}' created successfully![/green]\n"
        f"  Model: {final_template.get('model')}\n"
        f"  Provider: {final_template.get('provider')}\n"
        f"  Tools: {len(final_template.get('tools', []))}"
    )
    return 0
```

**Override priority:**
1. Template defaults (lowest)
2. Override file values
3. CLI arguments (highest)

### cmd_agent_templates()

```python
async def cmd_agent_templates(args: argparse.Namespace) -> int:
    templates = list_templates()
    
    if args.verbose:
        table = Table(title="Available Agent Templates (Detailed)")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Model", style="green")
        table.add_column("Provider", style="yellow")
        table.add_column("Tools", style="magenta")
        table.add_column("Loop", style="blue")
        
        for name in templates:
            template = get_template(name)
            tools_str = ", ".join(template.get("tools", []))
            table.add_row(name, template.get("description", ""), ...)
    else:
        table = Table(title="Available Agent Templates")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        
        for name in templates:
            template = get_template(name)
            table.add_row(name, template.get("description", ""))
    
    console.print(table)
    return 0
```

Uses `rich.table.Table` for formatted tabular output. Shows detailed columns in verbose mode.

### cmd_agent_info()

```python
async def cmd_agent_info(args: argparse.Namespace) -> int:
    if args.file:
        # Load from AGENT.md
        loader = AgentLoader()
        config = loader.load_from_markdown(Path(args.file))
        _display_agent_config(config)
    elif args.template:
        template = get_template(args.template)
        _display_template_config(template)
    
    return 0
```

Displays agent configuration in a formatted table.

### Display Functions

```python
def _display_agent_config(config: AgentConfig) -> None:
    table = Table(title=f"Agent Configuration: {config.name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Name", config.name)
    table.add_row("Model", config.model)
    table.add_row("Provider", config.provider)
    # ... etc
    
    console.print(table)
```

Uses Rich library for styled terminal tables.

---

## Inter-Module Data Flow

### CLI Create from File Flow
```
User runs: tinycua agent create ./my_agent
  → main() parses args
  → cmd_agent_create(args)
    → _create_from_file(args)
      → _validate_agent_path()
        → Check for ".."
        → Resolve absolute path
      → AgentLoader.load_from_markdown()
        → Parse AGENT.md
        → Return AgentConfig
      → Display config table
```

### CLI Create from Template Flow
```
User runs: tinycua agent create --template coder --model gpt-4o
  → main() parses args
  → cmd_agent_create(args)
    → _create_from_template(args)
      → get_template("coder")
      → _build_cli_overrides(args)
        → {"model": "gpt-4o"}
      → apply_template_overrides(template, overrides)
      → Display config table
```

### CLI List Templates Flow
```
User runs: tinycua agent templates --verbose
  → main() parses args
  → cmd_agent_templates(args)
    → list_templates()
    → For each template:
      → get_template(name)
      → Add row to Rich Table
    → console.print(table)
```
