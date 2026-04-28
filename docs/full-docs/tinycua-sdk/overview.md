# TINYCUA SDK - Project Overview

## What is TINYCUA SDK?

The `tinycua-sdk` is the **AI Agent Development Kit** for the TINYCUA ecosystem. It provides a Python SDK for building, configuring, running, and deploying AI agents that can use tools, manage memory, delegate to sub-agents, and integrate with LLM providers (OpenAI, Ollama, LM Studio, etc.).

**Version:** 0.1.0  
**Requires Python:** >= 3.12  
**Location in monorepo:** `src/tinycua-sdk/`

## Core Dependencies

| Package | Purpose |
|---------|---------|
| `httpx` | Async HTTP client for LLM APIs and backend communication |
| `pydantic` | Data validation and settings management |
| `python-ai-sdk` | AI SDK integration |
| `python-dotenv` | Environment variable loading |
| `pyyaml` | YAML parsing for agent/skill configs |
| `rich` | Terminal formatting for CLI |
| `sqlalchemy` | ORM for session/message storage |
| `tenacity` | Retry logic for API calls |

## Architecture Overview

The SDK follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                             │
│         (main.py, repl.py, agent_commands.py)               │
├─────────────────────────────────────────────────────────────┤
│                      Agent Layer                             │
│   (Agent → AgentExecutor → AgentDefinition → AgentConfig)   │
├─────────────────────────────────────────────────────────────┤
│                     Runner Layer                             │
│              (Runner - local execution engine)              │
├─────────────────────────────────────────────────────────────┤
│                   Client Layer                               │
│    (ResponsesClient, BackendClient, AgentClient)            │
├─────────────────────────────────────────────────────────────┤
│                    Tools Layer                               │
│   (Tool decorator, schema, resolver, parser, MCP)           │
├─────────────────────────────────────────────────────────────┤
│                   Memory Layer                               │
│   (ShortTermMemory, LongTermMemory, Cache, Compression)     │
├─────────────────────────────────────────────────────────────┤
│                   Storage Layer                              │
│   (SessionStore, SQLite, Models, Export/Import, Snapshot)   │
├─────────────────────────────────────────────────────────────┤
│                   Skills Layer                               │
│   (Loader, Registry, Models, Cache, Improver, Backend)      │
├─────────────────────────────────────────────────────────────┤
│              Security & Context Layer                        │
│   (Permissions, Approval, Discovery, Sanitizer, Injection)  │
├─────────────────────────────────────────────────────────────┤
│              Modeling & Middleware Layer                     │
│   (Personality, Profiler, UserModel, Hooks)                 │
├─────────────────────────────────────────────────────────────┤
│                    Core Layer                                │
│              (ToolRegistry, SDKConfig)                      │
└─────────────────────────────────────────────────────────────┘
```

## Core Concepts

### 1. Agent

The `Agent` class (`agent/agent.py`) is the primary user-facing API. It represents an AI agent with:
- **Configuration**: model, provider, system prompt, instructions
- **Tools**: functions the agent can call
- **Policy**: behavior settings (temperature, max tool calls)
- **Mode**: local execution vs. deployed (remote backend)
- **Sub-agents**: delegation to specialized child agents
- **Memory**: short-term (session) and long-term (persistent) memory

**Inheritance chain:**
```
Agent → AgentExecutor → AgentDefinition
```

This design separates concerns:
- `AgentDefinition`: Holds configuration and properties
- `AgentExecutor`: Adds execution capabilities (run, stream, cancel)
- `Agent`: Adds lifecycle convenience (deploy, delete, templates)

### 2. Runner

The `Runner` class (`runner/runner.py`) is the local execution engine. It:
- Builds LLM request messages
- Manages the tool execution loop
- Handles streaming responses
- Registers sub-agents as delegate tools
- Strips thinking tags from LLM outputs

### 3. Session

Sessions (`session/session.py`, `storage/store.py`) manage conversation state:
- `Session`: Simple file-based session persistence
- `SessionStore`: SQLAlchemy-based unified storage (SQLite/PostgreSQL)
- Supports message history, summaries, lineage (parent/child sessions)

### 4. Tools

Tools (`tools/decorators.py`) are functions decorated with `@tool` that the agent can invoke:
- Automatic JSON Schema generation from type hints
- Support for dependencies, versioning, bundling
- ToolRegistry singleton for centralized registration
- Security: permission levels and approval workflows

### 5. Memory

The memory system provides multiple tiers:
- **ShortTermMemory**: Thread-safe in-memory message window
- **LongTermMemory**: File-based persistent storage (MEMORY.md, USER.md)
- **PromptCache**: Anthropic-style caching with TTL and LRU eviction
- **ContextCompressor**: Token limit management via summarization/truncation

### 6. Skills

Skills (`skills/`) are reusable capability packages defined in `SKILL.md` files:
- YAML frontmatter for metadata
- Markdown for instructions
- Conditional activation based on platform/tool availability
- Auto-improvement tracking based on usage patterns

### 7. Custom Loops

The `BaseLoop` class (`agent/loop.py`) allows custom execution strategies:
- `DefaultLoop`: Standard tool loop via Runner
- `ReactLoop`: ReAct pattern (Reason + Act) with explicit reasoning
- Hook system for pre/post execution customization

### 8. Security

Security features include:
- **PermissionSystem**: SAFE / WARNING / DANGEROUS tool levels
- **ApprovalWorkflow**: Explicit approval for dangerous operations
- **InjectionDetector**: Prompt injection pattern scanning
- **MessageSanitizer**: Removes dangerous content before LLM calls
- **ToolResolver**: AST validation and subprocess isolation for inline tools

## Execution Modes

### Local Mode (Default)
```python
agent = Agent(name="assistant", model="gpt-4o-mini")
result = await agent.run("Hello!")
```

### Deployed Mode
```python
agent = Agent(mode="deployed", backend_url="...", agent_id="...")
result = await agent.run("Hello!")  # Calls backend API
```

## Data Flow

### Local Execution Flow
```
User Input → Agent.run() → BaseLoop.run() → Runner.run()
    → build_messages() → call_llm() → ResponsesClient.create()
    → LLM Response → extract_tool_calls() → execute_tool_loop()
    → Tool.invoke() → Result → Next LLM call (or final response)
```

### Streaming Flow
```
Agent.stream() → Runner.stream_with_tools() → ResponsesClient.stream()
    → Yield StreamEvent (CONTENT, TOOL_CALL_START, TOOL_RESULT_CHUNK, DONE)
```

### Deployed Execution Flow
```
Agent.run() → BackendClient.execute() → HTTP SSE Stream
    → Parse events → Accumulate response → Return text
```

## How It Fits Into TINYCUA Ecosystem

The SDK is the **client-side** component of TINYCUA:
- **tinycua-sdk**: This package - for building agents locally
- **tinycua backend**: Server that hosts deployed agents, manages tenants, persists sessions
- **tinycua CLI**: Command-line interface (some parts live in `cli/` here for backward compat)

The SDK can operate independently (local mode) or connect to a TINYCUA backend (deployed mode).

## Key Design Decisions

1. **Backward Compatibility**: Deprecated import shims have been removed. Use canonical import paths from the appropriate package (e.g., `tinycua_sdk.tools` for SDK tools, `tinycua.agent.tools` for CLI tools).

2. **Singleton ToolRegistry**: Centralized registry ensures tools registered anywhere are available everywhere.

3. **Lazy Imports**: Heavy dependencies (like `tinycua.agent.lifecycle`) are imported lazily to avoid circular dependencies and speed up module loading.

4. **Async-First**: All execution paths are async by default, with `_sync` wrappers for convenience.

5. **Environment Variable Substitution**: Config files support `${VAR_NAME}` syntax for secure credential injection.

6. **Subprocess Isolation**: Inline tool definitions execute in subprocesses with timeout protection.

7. **Thread Safety**: Memory and cache systems use `threading.RLock` for concurrent access.

## File Organization

```
tinycua_sdk/
├── __init__.py              # Public API exports
├── agent/                   # Agent definition, execution, loops, hooks
├── clients/                 # HTTP clients for LLM and backend APIs
├── cli/                     # Command-line interface
├── context/                 # Discovery, compression, sanitization, injection detection
├── core/                    # Registry and SDK configuration
├── events/                  # Event system (placeholder)
├── memory/                  # Short-term, long-term, cache, compression, plugins
├── middleware/              # Hook-based middleware system
├── modeling/                # Personality, profiler, user modeling
├── models/                  # Pydantic/dataclass models for requests/responses/results
├── runner/                  # Local execution engine
├── security/                # Permissions and approval workflows
├── session/                 # Session management
├── skills/                  # Skill loading, registry, caching, improvement
├── storage/                 # Unified storage layer (SQLAlchemy + SQLite)
├── tools/                   # Tool decorator, schema, resolver, parser, MCP
└── utils/                   # Utility functions
```
