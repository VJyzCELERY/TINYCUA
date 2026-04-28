# TUI Module Documentation

The TUI module provides a rich terminal user interface for TinyCUA using the **Textual** framework. It includes multiple screens, widgets, managers, and command handlers.

---

## Module Overview

| File | Purpose |
|------|---------|
| `tui/app.py` | Main Textual application and all screen definitions |
| `tui/chat.py` | Chat message management and history |
| `tui/commands.py` | Slash command parser for TUI input |
| `tui/widgets.py` | Custom Textual widgets (OutputPanel, StatusBar) |
| `tui/agent_manager.py` | Agent CRUD operations |
| `tui/agent_commands.py` | Agent-related slash command handlers |
| `tui/session_manager.py` | Session management for TUI |
| `tui/tool_manager.py` | Tool discovery and execution |
| `tui/skills_manager.py` | Skill loading and listing |
| `tui/export_import.py` | Export/import command handlers |
| `tui/sync_commands.py` | Sync/connection command handlers |

---

## `tui/app.py`

### Purpose

Defines the main Textual application (`TinyCUAApp`) and all screens. This is the largest file in the project (~1387 lines).

### Shared CSS

```python
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
```

This CSS is shared across multiple screens for consistent layout.

### `_validate_path()` Function

```python
def _validate_path(path: Path, *, must_exist: bool = False, allow_create_dir: bool = True) -> tuple[bool, str]:
```

Validates user-provided paths for **traversal safety**.

**Security checks:**
1. Resolves the path and checks for `..` components
2. Ensures the path is within allowed base directories:
   - User home directory
   - `/tmp` or system temp directory
   - `~/.tinycua` (default export directory)
3. Optionally checks if the path exists
4. Optionally checks if parent directory exists (when `allow_create_dir=False`)

**Why this matters:** Prevents directory traversal attacks where a malicious input like `/etc/passwd` or `../../../etc/passwd` could be used to access sensitive files.

### `ChatScreen` Class

The primary screen for agent interaction. Inherits from `Screen` plus three mixins for command handling.

```python
class ChatScreen(Screen, AgentCommandMixin, ExportImportCommandMixin, SyncCommandMixin):
```

**Initialization:**
```python
def __init__(
    self,
    session_manager: TuiSessionManager,
    agent_manager: AgentManager,
    tool_manager: ToolManager,
    skills_manager: SkillsManager,
) -> None:
```

Stores references to all managers and creates a `ChatInterface` and `CommandParser`.

**Compose layout:**
```python
def compose(self) -> ComposeResult:
    yield Header()
    yield Container(OutputPanel(id="output"), id="output-container")
    yield Container(Input(placeholder="Type a message or /command...", id="input"), id="input-container")
    yield StatusBar(id="status-bar")
    yield Footer()
```

Layout:
- Header at top
- OutputPanel (scrollable output area) taking remaining space
- Input field docked at bottom
- StatusBar showing current state
- Footer with key bindings

**On mount:**
- Updates status bar
- Displays current session name (if any)
- Shows welcome message

**Input handling:**
```python
async def on_input_submitted(self, event: Input.Submitted) -> None:
```

1. Gets and strips user input
2. Appends user message to output panel
3. Checks if it's a slash command via `CommandParser`
4. If command: dispatches to `_handle_command()`
5. If "quit"/"exit": exits app
6. Otherwise: processes as chat message via `_process_message()`
7. Clears input field

**Command dispatch:**
```python
async def _handle_command(self, command: str, args: str, output: OutputPanel) -> None:
    handler = getattr(self, f"_cmd_{command.replace('-', '_')}", None)
    if handler is not None:
        await handler(args, output)
    else:
        output.append_line(f"[red]Unknown command: /{command}[/red]")
```

Uses dynamic method lookup with name transformation (`agent-create` → `_cmd_agent_create`).

**Built-in commands in ChatScreen:**

| Command | Method | Description |
|---------|--------|-------------|
| `/help` | `_cmd_help` | Shows available commands |
| `/new` | `_cmd_new` | Creates new session |
| `/list` | `_cmd_list` | Lists all sessions |
| `/clear` | `_cmd_clear` | Clears output and chat |
| `/settings` | `_cmd_settings` | Opens SettingsScreen |
| `/quit` | `_cmd_quit` | Exits application |
| `/tools` | `_cmd_tools` | Lists available tools |
| `/skills` | `_cmd_skills` | Lists available skills |
| `/reload-skills` | `_cmd_reload_skills` | Reloads skills from directories |

**Message processing:**
```python
async def _process_message(self, message: str, output: OutputPanel) -> None:
```

1. Sets status to "Thinking..."
2. Gets current agent instance (from app, agent manager, or creates default)
3. Runs `agent.run(message)`
4. Appends assistant response to output
5. Updates status to "Ready" or "Error"

**Key navigation:**
```python
def on_key(self, event: Key) -> None:
```

- `up` arrow: Navigate to previous input in history
- `down` arrow: Navigate to next input in history

### `SessionsListScreen` Class

Screen for listing and managing sessions.

```python
class SessionsListScreen(Screen):
```

**Layout:** Centered container with session buttons, "New Session" button, and "Back to Chat" button.

**Features:**
- Populates session list on mount
- Marks current session with ` *`
- Clicking a session resumes it and returns to chat
- "New Session" creates a new session

### `SettingsScreen` Class

Simple settings display screen.

```python
class SettingsScreen(Screen):
```

Currently displays static text:
```
Mode: local
Agent: default
Theme: default
Auto-save: enabled
```

### `HelpScreen` Class

Displays help text from the `CommandParser`.

```python
class HelpScreen(Screen):
```

### `FileBrowserScreen` Class

File browser dialog using Textual's `DirectoryTree`.

```python
class FileBrowserScreen(Screen):
    def __init__(
        self,
        initial_path: Path | None = None,
        on_select: Callable[[Path], None] | None = None,
        select_file: bool = True,
    ) -> None:
```

**Features:**
- Displays current directory tree
- Updates path label on selection
- "Cancel" button dismisses screen
- "Select" button calls `on_select` callback and dismisses
- If `select_file=True`, prevents selecting directories

### `ConfirmScreen` Class

Simple confirmation dialog.

```python
class ConfirmScreen(Screen):
    def __init__(self, message: str, on_confirm: Callable[[], None]) -> None:
```

Shows a message with "No" and "Yes" buttons. Calls `on_confirm` callback if "Yes" is pressed.

### `ExportPreviewScreen` Class

Preview screen before executing an export.

```python
class ExportPreviewScreen(Screen):
```

**Features:**
- Shows export format and item counts (sessions, agents, memory, skills)
- Displays output path
- If file exists: shows warning with Overwrite/Rename/Cancel options
- If file doesn't exist: shows Export/Cancel options

**Export execution:**
```python
def _run_export(self, overwrite: bool = False, rename: bool = False) -> None:
```

Handles file collision scenarios with timestamp-based renaming.

### `ExportScreen` Class

Full export configuration screen.

```python
class ExportScreen(Screen):
```

**Features:**
- Checkboxes for data types (Sessions, Agents, Memory, Skills)
- Granular selection lists for specific sessions and agents
- Format radio buttons (JSON/ZIP)
- Output path input with browse button
- Live counts of available items

**On mount:**
- Sets default export path with timestamp
- Updates checkbox labels with item counts
- Populates selection lists

**Browse button:** Opens `FileBrowserScreen` to choose directory/file.

**Export button:** Parses selections, creates `ExportOptions`, and pushes `ExportPreviewScreen`.

### `ImportScreen` Class

Import data screen.

```python
class ImportScreen(Screen):
```

**Features:**
- File path input with browse button
- Live preview of import file (validation results)
- Mode selection (Merge/Replace)

**Preview update:**
```python
def _update_preview(self, path_str: str) -> None:
```

Validates the file and displays:
- Version
- Data types
- Warnings
- Errors

**Replace mode protection:** Shows `ConfirmScreen` before destructive replace operation.

### `TinyCUAApp` Class

The main Textual application.

```python
class TinyCUAApp(App):
    TITLE = "TinyCUA"
    SUB_TITLE = "Computer-Use Agent"
```

**Initialization:**
```python
def __init__(self) -> None:
    self._agent = None
    self._current_agent_instance = None
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
    self._remote_manager = None
    self._sync_engine = None
    self._local_memory_store = None
    self._local_session_store = None
```

**On mount lifecycle:**
```python
def on_mount(self) -> None:
    self._init_storage()
    self._init_agent()
    self._load_skills()
    self._create_default_session()
    self.push_screen(ChatScreen(...))
```

**Initialization methods:**

| Method | Purpose |
|--------|---------|
| `_init_agent()` | Initializes default agent via `AgentManager` |
| `_load_skills()` | Loads skills from configured directories |
| `_create_default_session()` | Creates "Default Session" if none exist |
| `_init_storage()` | Initializes SQLite database |

**Remote initialization:**
```python
def init_remote(self, backend_url: str, api_key: str | None = None) -> None:
```

Creates `RemoteConnectionManager` and `SyncEngine`.

**Sync method:**
```python
async def _sync_with_backend(self) -> bool:
```

Pushes all local sessions to remote backend via `SyncEngine.push_all()`.

**Getter methods:**

| Method | Returns |
|--------|---------|
| `get_remote_manager()` | `RemoteConnectionManager \| None` |
| `get_session_manager()` | `TuiSessionManager` |
| `get_agent_manager()` | `AgentManager` |
| `get_tool_manager()` | `ToolManager` |
| `get_skills_manager()` | `SkillsManager` |
| `get_storage_manager()` | `LocalStorageManager` |
| `get_memory_store()` | `LocalMemoryStore` (lazy init) |
| `get_session_store()` | `LocalSessionStore` (lazy init) |
| `get_export_manager()` | `ExportManager` (creates new instance) |
| `get_import_manager()` | `ImportManager` (creates new instance) |
| `get_sync_engine()` | `SyncEngine \| None` |
| `current_agent_instance` | Current agent (property with getter/setter) |

**Why lazy initialization for stores?** Prevents circular dependencies and unnecessary database connections during app startup.

---

## `tui/chat.py`

### Purpose

Manages chat messages, input history, and streaming response buffering.

### `ChatMessage` Dataclass

```python
@dataclass
class ChatMessage:
    role: MessageRole  # "user" | "assistant" | "tool"
    content: str
    timestamp: str | None = None
```

### `ChatInterface` Class

```python
class ChatInterface:
    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []
        self._input_history: list[str] = []
        self._history_index: int = -1
        self._streaming_buffer: str = ""
        self._is_streaming: bool = False
```

**Message management:**

| Method | Purpose |
|--------|---------|
| `add_user_message(content)` | Adds user message, also adds to input history |
| `add_assistant_message(content)` | Adds assistant message |
| `add_tool_message(content)` | Adds tool message |
| `get_formatted_messages()` | Returns Rich-formatted message string |
| `get_messages()` | Returns copy of all messages |
| `clear()` | Clears all messages |

**Input history navigation:**

```python
def get_previous_input(self) -> str | None:
    if not self._input_history:
        return None
    if self._history_index > 0:
        self._history_index -= 1
    return self._input_history[self._history_index]

def get_next_input(self) -> str | None:
    if not self._input_history:
        return None
    if self._history_index < len(self._input_history) - 1:
        self._history_index += 1
        return self._input_history[self._history_index]
    self._history_index = len(self._input_history)
    return ""
```

The history index starts at `-1` (before any history). As the user presses up, it decrements toward `0` (oldest). As the user presses down, it increments toward the end, with the last position returning an empty string (allowing new input).

**Streaming support:**

```python
def start_streaming(self) -> None:
    self._is_streaming = True
    self._streaming_buffer = ""

def append_stream_chunk(self, chunk: str) -> None:
    if self._is_streaming:
        self._streaming_buffer += chunk

def finalize_stream(self) -> str:
    if self._is_streaming and self._streaming_buffer:
        self.add_assistant_message(self._streaming_buffer)
    self._is_streaming = False
    result = self._streaming_buffer
    self._streaming_buffer = ""
    return result
```

Streaming is used for real-time agent responses where chunks arrive progressively.

---

## `tui/commands.py`

### Purpose

Parses slash commands entered in the TUI input field.

### `ParsedCommand` Dataclass

```python
@dataclass
class ParsedCommand:
    name: str
    args: str
```

### `CommandParser` Class

```python
class CommandParser:
    def __init__(self) -> None:
        self._commands: dict[str, str] = {
            "help": "Show available commands",
            "new": "Start a new chat session",
            "list": "List all sessions",
            "quit": "Exit the application",
            "clear": "Clear the current chat",
            "settings": "Open settings",
            "agents": "List all agents",
            "agent": "Switch to an agent",
            "agent-create": "Create a new agent",
            "tools": "List all available tools",
            "skills": "List all available skills",
            "reload-skills": "Reload skills from directories",
            "export": "Export data to file",
            "import": "Import data from file",
        }
```

**Parse logic:**
```python
def parse(self, text: str) -> ParsedCommand | None:
    text = text.strip()
    if not text.startswith("/"):
        return None
    parts = text[1:].split(maxsplit=1)
    command_name = parts[0].lower()
    if command_name not in self._commands:
        if command_name in ("agent",):
            return ParsedCommand(name=command_name, args=parts[1] if len(parts) > 1 else "")
        return None
    args = parts[1] if len(parts) > 1 else ""
    return ParsedCommand(name=command_name, args=args)
```

**Note:** The `/agent` command is special-cased because it accepts arbitrary agent names as arguments and isn't in the predefined command list.

---

## `tui/widgets.py`

### `OutputPanel` Class

Scrollable output display for agent responses.

```python
class OutputPanel(Static):
    DEFAULT_CSS = """
    OutputPanel {
        height: 1fr;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    """
```

**Methods:**
- `append_line(line)` — Appends a line and updates display
- `clear_output()` — Clears all lines

**Implementation:** Stores lines in `self._lines: list[str]` and joins them with `\n` on each update. Simple but potentially inefficient for very large outputs.

### `StatusBar` Class

Status bar showing connection and agent state.

```python
class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary-darken-1;
        color: $text;
        padding: 0 1;
    }
    """
```

**State:**
- `_status` — Connection status ("Disconnected", "Ready", "Error", etc.)
- `_agent` — Current agent name
- `_mode` — Execution mode ("local", "remote", "deployed")

**Format:**
```
Status: Ready | Agent: assistant | Mode: local
```

---

## `tui/session_manager.py`

### `TuiSessionManager` Class

Manages sessions for the TUI using the SDK's `SessionStore`.

```python
class TuiSessionManager:
    def __init__(self, store: SessionStore | None) -> None:
        self._store = store
        self._current_session_id: uuid.UUID | None = None
        self._sessions: list[Any] = []
```

**Methods:**

| Method | Purpose |
|--------|---------|
| `create_session(name)` | Creates new session, sets as current |
| `list_sessions()` | Lists all sessions |
| `delete_session(session_id)` | Deletes session, clears current if matched |
| `set_current_session(session_id)` | Sets current session ID |
| `get_current_session()` | Gets current session object |
| `resume_session(session_id)` | Gets session and sets as current |
| `get_current_session_id()` | Returns current session UUID |

**Store access:**
```python
def _get_store(self) -> SessionStore:
    if self._store is None:
        raise ValueError("No session store provided.")
    return self._store
```

**Error handling:** All store operations are wrapped in try/except blocks that log exceptions and return safe defaults.

---

## `tui/tool_manager.py`

### `ToolInfo` Dataclass

```python
@dataclass
class ToolInfo:
    name: str
    description: str
    toolset: str | None = None
```

### `ToolManager` Class

```python
class ToolManager:
    def __init__(self) -> None:
        self._registry = ToolRegistry()
        self._loaded_tools: dict[str, ToolInfo] = {}
```

**Note on `list_tools()`:** The implementation accesses `self._registry._tools` directly because `ToolRegistry` does not expose a public method to list all tools. This is documented as a workaround.

```python
for tool_name, entry in self._registry._tools.items():
    tool_info = ToolInfo(
        name=tool_name,
        description=entry.description or "No description",
        toolset=entry.toolset,
    )
```

**`execute_tool()`:**
```python
async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
    entry = self._registry._tools.get(tool_name)
    handler = entry.handler
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: handler(arguments))
    return str(result)
```

Tools are executed in a thread pool because SDK tool handlers may be synchronous.

---

## `tui/skills_manager.py`

### `SkillInfo` Dataclass

```python
@dataclass
class SkillInfo:
    name: str
    description: str
    category: str
    path: Path
```

### `SkillsManager` Class

```python
class SkillsManager:
    DEFAULT_SKILL_DIRS = [
        Path.home() / ".tinycua" / "skills",
        Path(__file__).parent.parent.parent.parent / "skills",
    ]
```

**Skill directories:**
1. `~/.tinycua/skills` — User skills
2. `../../skills` relative to package — Built-in skills

**Methods:**

| Method | Purpose |
|--------|---------|
| `load_skills()` | Discovers and loads skills from directories |
| `reload_skills()` | Clears and reloads all skills |
| `list_skills()` | Returns loaded skills (auto-loads if not loaded) |
| `get_skill(name)` | Gets skill by name |
| `get_skills_by_category(category)` | Filters by category |
| `get_categories()` | Returns unique categories |
| `add_skill_directory(directory)` | Adds additional search path |

---

## `tui/agent_manager.py`

### `AgentInfo` Dataclass

```python
@dataclass
class AgentInfo:
    id: uuid.UUID
    name: str
    config: AgentConfig
```

### `AgentManager` Class

Manages agent configurations stored as JSON files in `~/.tinycua/agents/`.

```python
class AgentManager:
    def __init__(self) -> None:
        self._agents: dict[uuid.UUID, AgentInfo] = {}
        self._current_agent_id: uuid.UUID | None = None
        self._default_agent: Agent | None = None
```

**Agent storage:** Each agent is saved as `{agent_id}.json` in `~/.tinycua/agents/`.

**`create_agent()`:**
```python
def create_agent(
    self,
    name: str,
    model: str = DEFAULT_MODEL,
    provider: str = DEFAULT_PROVIDER,
    base_url: str | None = None,
    api_key: str | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    instructions: str = "",
    temperature: float = 1.0,
    max_turns: int | None = None,
) -> AgentInfo | None:
```

Creates an `AgentConfig` with `AgentPolicy`, saves to file, and caches in memory.

**`create_agent_instance()`:**
```python
def create_agent_instance(self, agent_info: AgentInfo) -> Agent | None:
```

Creates a live `Agent` object from stored `AgentInfo` using the SDK's `Agent` class.

**`init_default_agent()`:**
```python
def init_default_agent(self) -> Agent | None:
```

Delegates to `tinycua.agent.default_agent.create_default_agent()`.

---

## `tui/agent_commands.py`

### `AgentCommandMixin` Class

Provides agent-related slash command handlers for `ChatScreen`.

**Commands:**

| Command | Method | Description |
|---------|--------|-------------|
| `/agents` | `_cmd_agents` | Lists all agents, marks current with `*` |
| `/agent <name>` | `_cmd_agent` | Switches to named agent |
| `/agent-create <name>` | `_cmd_agent_create` | Creates new agent with options |

**`/agent-create` options:**
- `--model`
- `--provider`
- `--base-url`
- `--api-key`
- `--system-prompt`
- `--instructions`
- `--temperature`
- `--max-turns`

**Agent switching flow:**
```python
if self._agent_manager.set_current_agent(target.id):
    agent_instance = self._agent_manager.create_agent_instance(target)
    if agent_instance:
        self.app.current_agent_instance = agent_instance
        self._update_status_bar()
```

---

## `tui/export_import.py`

### `ExportImportCommandMixin` Class

Provides export and import command handlers.

**`/export` command:**
- Without args: Opens `ExportScreen` (full GUI)
- With args: Parses options and opens `ExportPreviewScreen`

**`parse_export_args()`:**
```python
def parse_export_args(args: str) -> tuple[ExportOptions, Path, str]:
```

Supports flags:
- `--no-sessions`
- `--no-agents`
- `--no-memory`
- `--no-skills`
- `--format json|zip`

**`/import` command:**
- Without args: Opens `ImportScreen` (full GUI)
- With args: Validates path and performs import

**Security note:** Replace mode is blocked from CLI and requires the Import screen to prevent accidental data loss.

---

## `tui/sync_commands.py`

### `SyncCommandMixin` Class

Provides sync-related command handlers.

**`/connect <url> [--api-key KEY]`:**
```python
async def _cmd_connect(self, args: str, output: OutputPanel) -> None:
```

Parses URL and optional API key, then calls `self.app.init_remote()`.

**`/sync`:**
```python
async def _cmd_sync(self, args: str, output: OutputPanel) -> None:
```

Checks remote connection and calls `sync_engine.push_all()`.

---

## TUI Data Flow

```
User types in Input widget
    │
    ▼
ChatScreen.on_input_submitted()
    │
    ├─ Slash command? ──▶ CommandParser.parse()
    │                        │
    │                        ▼
    │                   _handle_command()
    │                        │
    │                        ▼
    │                   Dynamic method dispatch
    │                   (mixin handlers)
    │
    └─ Regular message ──▶ _process_message()
                              │
                              ▼
                         Get current agent
                              │
                              ▼
                         agent.run(message)
                              │
                              ▼
                         Display result in OutputPanel
                              │
                              ▼
                         Update StatusBar
```

## Why Textual?

Textual was chosen over other TUI frameworks because:
1. **Python-native** — No C extensions or external dependencies
2. **Reactive** — Built-in reactive programming model fits async agent operations
3. **CSS-like styling** — Familiar styling syntax
4. **Widget ecosystem** — Includes DirectoryTree, Input, Button, etc.
5. **Async support** — Native `async`/`await` support for agent calls

## Screen Navigation

```
TinyCUAApp (mounts ChatScreen by default)
    │
    ├─ push_screen(SessionsListScreen)
    │      └─ pop_screen() → back to ChatScreen
    │
    ├─ push_screen(SettingsScreen)
    │      └─ pop_screen() → back to ChatScreen
    │
    ├─ push_screen(HelpScreen)
    │      └─ pop_screen() → back to ChatScreen
    │
    ├─ push_screen(FileBrowserScreen)
    │      └─ pop_screen() → back to caller
    │
    ├─ push_screen(ConfirmScreen)
    │      └─ pop_screen() → back to caller
    │
    ├─ push_screen(ExportScreen)
    │      └─ push_screen(ExportPreviewScreen)
    │             └─ pop_screen() → back to ExportScreen or ChatScreen
    │
    └─ push_screen(ImportScreen)
           └─ push_screen(ConfirmScreen) [for replace mode]
                  └─ pop_screen() → back to ImportScreen or ChatScreen
```
