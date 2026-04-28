# CLI Module Documentation

The CLI module provides the command-line interface for TinyCUA. It consists of three main files:

- **`cli/main.py`** — Entry point and argument parsing
- **`cli/commands.py`** — Async command handlers
- **`cli/repl.py`** — Interactive REPL with prompt-toolkit

---

## `cli/main.py`

### Purpose

This is the primary entry point for the `tinycua` command. It sets up argument parsing with `argparse`, handles the setup wizard on first startup, and dispatches to the appropriate command handler.

### `main()` Function

```python
def main() -> int:
```

Returns an exit code (0 for success, 1 for errors).

**Argument Parser Setup:**

```python
parser = argparse.ArgumentParser(
    prog="tinycua",
    description="TINYCUA - Computer-Use Agent CLI",
)
```

**Global Flags:**
- `--no-wizard` — Skip setup wizard on first startup
- `--force-wizard` — Force run setup wizard

**Subcommands:**

| Subcommand | Purpose | Arguments |
|-----------|---------|-----------|
| `repl` | Start interactive REPL | None |
| `run` | Run agent with input | `input` (optional positional), `--file` |
| `deploy` | Deploy agent to backend | `file` (optional), `--backend-url`, `--api-key` |
| `chat` | Start interactive chat session | `--agent` |
| `tui` | Launch Textual TUI application | None |
| `agent` | Manage agents | Sub-subcommands: `create`, `templates`, `info` |

**The `agent create` subcommand** accepts extensive overrides:
- `path` — Path to AGENT.md file or directory
- `--template` — Template name (coder, researcher, assistant)
- `--model` — Override model (e.g., gpt-4o, gpt-5-nano)
- `--provider` — Override provider (e.g., openai, openai-compatible)
- `--tools` — Comma-separated tool list
- `--skills` — Comma-separated skill list
- `--loop` — Loop type (default, react, plan)
- `--temperature` — Temperature 0.0-2.0
- `--override-file` — JSON/YAML file with overrides

**Wizard Logic:**

```python
if args.command is None or args.force_wizard or (not args.no_wizard and args.command in ("repl", "chat", "tui", None)):
    from tinycua.config import is_first_startup, run_wizard
    if args.force_wizard or is_first_startup():
        run_wizard()
        if args.command is None:
            return 0
```

The wizard runs automatically when:
- No command is given
- The command is `repl`, `chat`, or `tui`
- `--force-wizard` is set
- It's the first startup (no config, db, or credentials exist)

**Command Dispatch:**

```python
if args.command == "repl":
    from tinycua.cli.repl import run_repl
    return run_repl()

if args.command == "run":
    from tinycua.cli.commands import cmd_run
    return asyncio.run(cmd_run(args))
```

Commands that need async handlers are wrapped with `asyncio.run()`. The `agent` subcommand delegates to `tinycua_sdk.cli.agent_commands` for `create`, `templates`, and `info`.

---

## `cli/commands.py`

### Purpose

Contains async command handlers for all CLI subcommands except `repl`. Uses `rich.console.Console` for colored output.

### `cmd_run(args)`

```python
async def cmd_run(args: argparse.Namespace) -> int:
```

Runs the agent with either a direct input string or a script file.

**Logic:**
1. Creates a default agent via `create_default_agent()`
2. If `--file` is provided, reads the file content
3. If positional `input` is provided, uses it directly
4. Requires at least one input source
5. Runs `agent.run(user_input)` and prints the result

**Error handling:** Catches `OSError`, `ValueError`, `TypeError` and prints red error messages.

```python
agent = create_default_agent()
if hasattr(args, "file") and args.file:
    file_path = Path(args.file)
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        return 1
    user_input = file_path.read_text()
# ...
result = await agent.run(user_input)
console.print(f"[green]{result}[/green]")
```

### `cmd_deploy(args)`

```python
async def cmd_deploy(args: argparse.Namespace) -> int:
```

Deploys the agent and its tools to a backend server.

**Logic:**
1. Optionally validates an agent definition file (not yet implemented)
2. Creates a default agent
3. Extracts `backend_url` and `api_key` from args
4. Creates an `AgentLifecycle` instance
5. Calls `lifecycle.deploy()` and prints deployment result

```python
lifecycle = AgentLifecycle(
    agent,
    backend_url=backend_url,
    backend_api_key=api_key,
)
result = await lifecycle.deploy()
console.print(f"  Agent ID: {result.get('id', 'unknown')}")
console.print(f"  Status: {result.get('status', 'unknown')}")
```

### `cmd_chat(args)`

```python
async def cmd_chat(args: argparse.Namespace) -> int:
```

Starts an interactive chat session in the terminal.

**Features:**
- Prints welcome banner: "TinyCUA Chat"
- Reads user input with `console.input("[bold blue]You>[/bold blue] ")`
- Handles `quit`/`exit` to leave
- Runs `agent.run(user_input)` and displays assistant response
- Handles `KeyboardInterrupt` gracefully
- Handles `EOFError` (Ctrl+D) to exit

```python
while True:
    user_input = await asyncio.to_thread(console.input, "[bold blue]You>[/bold blue] ")
    user_input = user_input.strip()
    if user_input.lower() in ("quit", "exit"):
        break
    result = await agent.run(user_input)
    console.print(f"[green]Assistant: {result}[/green]\n")
```

Note: `asyncio.to_thread()` is used because `console.input()` is blocking.

### `cmd_tui(args)`

```python
async def cmd_tui(args: argparse.Namespace) -> int:
```

Launches the Textual TUI application.

**Logic:**
1. Imports `TinyCUAApp` from `tinycua.tui.app`
2. Creates an instance and runs it asynchronously
3. Catches `ImportError` if Textual is not installed and suggests `pip install tinycua[tui]`

```python
app = TinyCUAApp()
await app.run_async()
```

---

## `cli/repl.py`

### Purpose

Provides an interactive REPL (Read-Eval-Print Loop) using `prompt-toolkit` for enhanced editing, history, and tab completion.

### Constants

```python
SLASH_COMMANDS = [
    "/connect", "/status", "/agents", "/chat",
    "/run", "/deploy", "/help", "/quit",
    "/clear", "/history",
]
```

### `REPLCommandHandler` Class

The core class managing all REPL slash commands.

```python
class REPLCommandHandler:
    def __init__(self) -> None:
        self._backend_url: str | None = None
        self._backend_client: Any = None
        self._connected: bool = False
        self._chat_history: list[dict[str, str]] = []
```

**Attributes:**
- `_backend_url` — Currently connected backend URL
- `_backend_client` — `BackendClient` instance
- `_connected` — Connection state
- `_chat_history` — List of chat turns for `/history`

#### `handle_connect(url)`

Connects to a backend server.

```python
async def handle_connect(self, url: str) -> str:
```

**Logic:**
1. Sets `_backend_url`
2. Closes any existing client
3. Creates a new `BackendClient`
4. Performs a health check
5. Returns colored status message

**Error handling:** Catches `ConnectionError`, `OSError`, `ValueError`, `httpx.HTTPStatusError`.

#### `handle_status()`

Shows connection and agent status.

```python
async def handle_status(self) -> str:
```

Returns a multi-line string with:
- Backend URL
- Connected status
- Chat history turn count

#### `handle_agents()`

Lists available agents on the backend.

```python
async def handle_agents(self) -> str:
```

Requires an active connection. Calls `backend_client.list_agents()` and formats the results.

#### `handle_chat(agent_name)`

Starts an interactive chat session within the REPL.

```python
async def handle_chat(self, agent_name: str) -> str:
```

**Logic:**
1. Creates a default agent
2. Sets the agent name
3. Enters a nested loop reading user input
4. Handles `back`, `quit`, `exit` to return to REPL
5. Appends turns to `_chat_history`

Note: This uses synchronous `console.input()` (not async) because it's a nested loop.

#### `handle_run(file_path)`

Runs a script file through the agent.

```python
async def handle_run(self, file_path: str) -> str:
```

Validates the file exists, reads it, creates a default agent, and runs the content.

#### `handle_deploy(file_path)`

Deploys tools from a file.

```python
async def handle_deploy(self, file_path: str) -> str:
```

Currently uses the default agent (loading from file is not yet implemented). Creates an `AgentLifecycle` and deploys.

#### `handle_help()`

Returns formatted help text for all slash commands.

#### `handle_quit()`

Prints goodbye message and signals exit.

#### `handle_clear()`

Clears the console screen via `console.clear()`.

#### `handle_history()`

Returns formatted chat history from `_chat_history`.

### `_get_history_path()`

```python
def _get_history_path() -> Path:
```

Returns the path to the REPL history file: `~/.tinycua/repl_history`. Creates the directory if needed.

### `_run_repl_async()`

```python
async def _run_repl_async() -> int:
```

The main REPL loop.

**Setup:**
```python
history_path = _get_history_path()
session = PromptSession(
    history=FileHistory(str(history_path)),
    completer=WordCompleter(SLASH_COMMANDS, ignore_case=True),
)
handler = REPLCommandHandler()
```

**Loop:**
1. Prompts with `session.prompt("> ")` (runs in executor to avoid blocking)
2. Strips input
3. If starts with `/`, dispatches to `_handle_slash_command()`
4. Otherwise, prints a dim message indicating it would send to agent

### `run_repl()`

```python
def run_repl() -> int:
```

Wrapper that calls `asyncio.run(_run_repl_async())`.

### `_handle_slash_command()`

```python
async def _handle_slash_command(command: str, handler: REPLCommandHandler) -> str | None:
```

Parses slash commands and dispatches to the appropriate handler.

**Dispatch logic:**

| Command | Handler | Notes |
|---------|---------|-------|
| `/quit` | `handle_quit()` | Returns `None` to signal exit |
| `/help` | `handle_help()` | |
| `/clear` | `handle_clear()` | Returns `None` (no output) |
| `/connect` | `handle_connect(arg)` | Requires URL argument |
| `/status` | `handle_status()` | |
| `/agents` | `handle_agents()` | |
| `/chat` | `handle_chat(arg)` | Defaults to "assistant" if no arg |
| `/run` | `handle_run(arg)` | Requires file path |
| `/deploy` | `handle_deploy(arg)` | Requires file path |
| `/history` | `handle_history()` | |

**Argument parsing:**
```python
parts = command.split(maxsplit=1)
cmd = parts[0].lower()
arg = parts[1] if len(parts) > 1 else ""
```

---

## Data Flow: CLI Commands

```
User types: tinycua run "hello"
    │
    ▼
main() parses args
    │
    ▼
asyncio.run(cmd_run(args))
    │
    ▼
cmd_run():
  ├─ create_default_agent()
  ├─ agent.run("hello")
  └─ print result
```

```
User types: tinycua repl
    │
    ▼
main() calls run_repl()
    │
    ▼
asyncio.run(_run_repl_async())
    │
    ▼
REPL loop:
  ├─ prompt-toolkit reads input
  ├─ slash command? → dispatch to handler
  └─ regular text → echo (or send to agent)
```

## Error Handling Patterns

All CLI commands follow a consistent error handling pattern:

```python
try:
    # ... operation ...
    return 0
except (OSError, ValueError, TypeError) as e:
    console.print(f"[red]Error: {e}[/red]")
    return 1
```

This catches:
- **OSError** — File not found, permission denied, network errors
- **ValueError** — Invalid arguments, configuration errors
- **TypeError** — Type mismatches in SDK calls

The REPL uses a different pattern: errors are caught and returned as colored strings rather than exiting.

## Why These Design Choices?

1. **`argparse` over `click`/`typer`**: Keeps dependencies minimal. argparse is in the standard library.

2. **`asyncio.run()` per command**: Each async command gets its own event loop, keeping the entry point synchronous.

3. **`prompt-toolkit` for REPL**: Provides history, completion, and cross-platform input handling that raw `input()` cannot match.

4. **Lazy imports in `main.py`**: Commands only import their dependencies when executed, reducing startup time.

5. **Rich console for output**: Consistent colored output across all commands without complex formatting code.

6. **REPLCommandHandler class**: Encapsulates all REPL state (connection, history) in a single object, making it easier to test and extend.
