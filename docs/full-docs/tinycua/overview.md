# TinyCUA Overview

## What is TinyCUA?

TinyCUA is the **CLI/TUI application** layer of the TINYCUA (Tiny Computer-Use Agent) ecosystem. It provides the primary user-facing interface for interacting with AI agents that can control computers, manage conversations, and execute automated tasks.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     TinyCUA Application                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   CLI Layer │  │   TUI Layer │  │   Agent Core        │ │
│  │   (cli/)    │  │   (tui/)    │  │   (agent/)          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Storage   │  │   Remote    │  │   Config            │ │
│  │   (storage/)│  │   (remote/) │  │   (config/)         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐                          │
│  │   Clients   │  │   Tools     │                          │
│  │   (clients/)│  │   (tools/)  │                          │ │
│  └─────────────┘  └─────────────┘                          │ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   tinycua-sdk     │
                    │   (Python SDK)    │
                    └───────────────────┘
```

## How TinyCUA Fits into the TINYCUA Ecosystem

The TINYCUA ecosystem consists of multiple layers:

1. **tinycua-sdk**: The core Python SDK providing agent logic, tool registries, storage models, and LLM abstractions.
2. **tinycua (this project)**: The CLI/TUI application that wraps the SDK with user interfaces, local storage, remote sync, and configuration management.
3. **Backend Server**: Optional remote server for deploying agents, multi-user access, and centralized storage.

TinyCUA is the **main entry point** for end users. It imports `tinycua_sdk` for all core functionality and adds:
- Interactive terminal UI (Textual)
- Command-line interface (argparse + prompt-toolkit)
- Local SQLite storage wrappers
- Import/export data migration
- Remote synchronization
- First-time setup wizard

## Main Entry Points

### 1. CLI Entry Point: `tinycua/cli/main.py`

The `main()` function is the primary entry point when running `tinycua` from the command line.

**Key features:**
- Argument parsing with subcommands (`repl`, `run`, `deploy`, `chat`, `tui`, `agent`)
- Automatic setup wizard on first startup
- Lazy imports to minimize startup time

**Command structure:**
```bash
tinycua                          # Auto-runs wizard on first use
tinycua repl                     # Interactive REPL
tinycua run "hello"              # Run agent with input
tinycua run --file script.txt    # Run agent with file
tinycua deploy                   # Deploy to backend
tinycua chat                     # Interactive chat
tinycua tui                      # Launch TUI
tinycua agent create ...         # Agent management
tinycua agent templates          # List templates
tinycua agent info               # Show agent info
```

### 2. TUI Entry Point: `tinycua/cli/commands.py` → `tinycua/tui/app.py`

The `tinycua tui` command launches a full Textual-based terminal UI.

**Key features:**
- Multi-screen interface (Chat, Sessions, Settings, Help, File Browser)
- Real-time agent interaction with streaming support
- Slash commands (`/help`, `/new`, `/export`, `/import`, `/connect`, `/sync`)
- Mouse and keyboard support

### 3. REPL Entry Point: `tinycua/cli/repl.py`

The `tinycua repl` command launches an interactive REPL with prompt-toolkit.

**Key features:**
- Command history (stored in `~/.tinycua/repl_history`)
- Tab completion for slash commands
- Backend connection management
- Chat sessions within REPL

## Dependencies on tinycua-sdk

TinyCUA heavily depends on `tinycua_sdk` for all core functionality:

| TinyCUA Module | tinycua-sdk Dependency | Purpose |
|---------------|------------------------|---------|
| `agent/default_agent.py` | `tinycua_sdk.agent.agent.Agent` | Core agent instance |
| `agent/lifecycle.py` | `tinycua_sdk.tools.resolver` | Tool dependency resolution |
| `tui/tool_manager.py` | `tinycua_sdk.core.registry.ToolRegistry` | Tool discovery |
| `tui/skills_manager.py` | `tinycua_sdk.skills.loader.SkillLoader` | Skill loading |
| `storage/local_storage.py` | `tinycua_sdk.storage.store.SessionStore` | Session storage |
| `storage/local_session_store.py` | `tinycua_sdk.storage.models.Session` | Session models |
| `config/user_config.py` | `tinycua_sdk.core.config.SDKConfig` | Configuration models |
| `clients/backend.py` | N/A (httpx only) | HTTP client for backend |

## Project Structure

```
src/tinycua/tinycua/
├── __init__.py              # Package init, version
├── constants.py             # Default constants (model, provider, prompts)
├── exceptions.py            # Custom exceptions hierarchy
│
├── cli/                     # Command-line interface
│   ├── __init__.py
│   ├── main.py              # Entry point, argument parsing
│   ├── commands.py          # Async command handlers
│   └── repl.py              # Interactive REPL
│
├── tui/                     # Terminal UI
│   ├── __init__.py
│   ├── app.py               # Main Textual app + screens
│   ├── chat.py              # Chat message management
│   ├── commands.py          # Slash command parser
│   ├── widgets.py           # Custom Textual widgets
│   ├── agent_manager.py     # Agent CRUD
│   ├── agent_commands.py    # Agent command handlers
│   ├── session_manager.py   # Session management
│   ├── tool_manager.py      # Tool listing/execution
│   ├── skills_manager.py    # Skill discovery
│   ├── export_import.py     # Export/import handlers
│   └── sync_commands.py     # Sync command handlers
│
├── agent/                   # Agent core
│   ├── __init__.py
│   ├── default_agent.py     # Default agent factory
│   ├── lifecycle.py         # Deploy/delete/load operations
│   └── tools/               # Agent tools
│       ├── __init__.py
│       ├── context_tools.py # Session context tools
│       ├── memory_tools.py  # Memory storage tools
│       └── cua/             # Computer-use tools
│           ├── __init__.py
│           ├── keyboard.py
│           ├── mouse.py
│           └── screen_capture.py
│
├── storage/                 # Local storage
│   ├── __init__.py
│   ├── local_storage.py     # Storage manager
│   ├── local_memory_store.py # Key-value memory
│   ├── local_session_store.py # Session wrapper
│   ├── export_manager.py    # Data export
│   └── import_manager.py    # Data import
│
├── remote/                  # Remote sync
│   ├── __init__.py
│   ├── connection_manager.py # Backend connection
│   └── sync_engine.py       # Sync logic
│
├── config/                  # Configuration
│   ├── __init__.py
│   ├── user_config.py       # Config load/save
│   └── wizard.py            # First-time setup
│
└── clients/                 # HTTP clients
    ├── __init__.py
    └── backend.py           # Backend HTTP client
```

## Data Flow

### Typical User Interaction Flow

```
User Input
    │
    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  CLI/TUI    │────▶│   Agent     │────▶│   LLM       │
│  Interface  │     │  (SDK)      │     │  (Ollama/   │
│             │◀────│             │◀────│   OpenAI)   │
└─────────────┘     └─────────────┘     └─────────────┘
    │
    ▼
┌─────────────┐     ┌─────────────┐
│  Session    │────▶│  SQLite     │
│  Store      │     │  Database   │
└─────────────┘     └─────────────┘
```

### Agent Execution Flow

```
1. User sends message
2. Agent (SDK) processes message
3. LLM generates response (possibly with tool calls)
4. Tools execute (memory, context, CUA)
5. Results stored in session
6. Response displayed to user
```

### Remote Sync Flow

```
1. User runs /connect <url>
2. RemoteConnectionManager validates URL
3. BackendClient authenticates
4. SyncEngine pushes/pulls sessions
5. OfflineQueue handles disconnections
```

## Key Design Decisions

1. **Lazy Imports**: Most modules use lazy imports to avoid heavy dependencies at startup. For example, `tinycua_sdk` is imported inside functions rather than at module level.

2. **Singleton Pattern**: `LocalStorageManager` uses a singleton pattern to ensure only one database connection pool exists.

3. **Graceful Degradation**: CUA tools (keyboard, mouse, screen capture) have stub implementations when dependencies (`pyautogui`, `mss`, `Pillow`) are not installed.

4. **Three-way Config Merge**: Configuration uses YAML > env > defaults priority.

5. **Mixin Pattern**: TUI command handlers are split into mixins (`AgentCommandMixin`, `ExportImportCommandMixin`, `SyncCommandMixin`) to keep `ChatScreen` manageable.

6. **Type Checking Guards**: `TYPE_CHECKING` blocks prevent circular imports while maintaining type hints.

## Version

Current version: `0.1.0` (defined in `tinycua/__init__.py`)
