# TINYCUA Full Documentation Index

Welcome to the comprehensive documentation for the TINYCUA project. This documentation is designed to help developers use the projects and help contributors understand every part of the codebase.

## Documentation Structure

```
docs/full-docs/
├── INDEX.md                          # This file — master navigation
├── FINDINGS-TO-BE-REMOVED.md         # Deprecated/unused features tracking
├── tinycua/
│   ├── overview.md                   # Project overview & architecture
│   ├── cli.md                        # Command-line interface
│   ├── tui.md                        # Textual TUI application
│   ├── agent.md                      # Agent lifecycle & defaults
│   ├── storage.md                    # Local storage & export/import
│   ├── remote.md                     # Remote connection & sync
│   ├── config.md                     # User config & setup wizard
│   ├── clients.md                    # Backend client
│   └── tools.md                      # CUA tools (keyboard, mouse, screen)
├── tinycua-sdk/
│   ├── overview.md                   # SDK overview & core concepts
│   ├── agent.md                      # Agent, Executor, Definition, Loops
│   ├── clients.md                    # BackendClient, AgentClient, Protocol
│   ├── tools.md                      # Tool decorators, schema, resolver
│       ├── memory.md                     # Short-term, long-term & session memory
│   ├── session.md                    # Session management
│   ├── storage.md                    # SQLite storage, export/import
│   ├── skills.md                     # Skills loader, registry, cache
│   ├── runner.md                     # Runner execution engine
│   ├── models.md                     # Request/response data models
│   ├── security.md                   # Permissions & approval workflows
│   ├── middleware.md                 # Hook middleware system
│   ├── context.md                    # Context discovery & compression
│   ├── modeling.md                   # Personality & user modeling
│   ├── cli.md                        # SDK CLI & REPL
│   └── core.md                       # Registry & config core utilities
└── tinycua-backend/
    ├── overview.md                   # Backend overview & architecture
    ├── main.md                       # FastAPI app & lifespan
    ├── api.md                        # API endpoints (auth, sessions, messages)
    ├── auth.md                       # Authentication & authorization
    ├── storage.md                    # Database models & search backends
    ├── sync.md                       # Multi-device sync system
    ├── tenant.md                     # Tenant management
    ├── config.md                     # Configuration system
    └── migrations.md                 # Database migrations
```

---

## Quick Start by Role

### I want to **use** TINYCUA as a developer

1. Start with the SDK: [`tinycua-sdk/overview.md`](tinycua-sdk/overview.md)
2. Learn how to create agents: [`tinycua-sdk/agent.md`](tinycua-sdk/agent.md)
3. Add tools to your agent: [`tinycua-sdk/tools.md`](tinycua-sdk/tools.md)
4. Deploy to the backend: [`tinycua-sdk/clients.md`](tinycua-sdk/clients.md)
5. Use the CLI/TUI: [`tinycua/cli.md`](tinycua/cli.md) and [`tinycua/tui.md`](tinycua/tui.md)

### I want to **contribute** to the codebase

1. Understand the overall architecture: [`tinycua-sdk/overview.md`](tinycua-sdk/overview.md) → [`tinycua-backend/overview.md`](tinycua-backend/overview.md) → [`tinycua/overview.md`](tinycua/overview.md)
2. Dive into the area you want to change:
   - **Agent execution flow:** [`tinycua-sdk/agent.md`](tinycua-sdk/agent.md) → [`tinycua-sdk/runner.md`](tinycua-sdk/runner.md)
   - **Backend API:** [`tinycua-backend/main.md`](tinycua-backend/main.md) → [`tinycua-backend/api.md`](tinycua-backend/api.md)
   - **Authentication:** [`tinycua-backend/auth.md`](tinycua-backend/auth.md)
   - **Storage layer:** [`tinycua-backend/storage.md`](tinycua-backend/storage.md) + [`tinycua-sdk/storage.md`](tinycua-sdk/storage.md)
   - **Memory system:** [`tinycua-sdk/memory.md`](tinycua-sdk/memory.md)
   - **Skills system:** [`tinycua-sdk/skills.md`](tinycua-sdk/skills.md)
   - **TUI screens:** [`tinycua/tui.md`](tinycua/tui.md)
   - **Remote sync:** [`tinycua/remote.md`](tinycua/remote.md)

### I want to **remove deprecated code**

See [`FINDINGS-TO-BE-REMOVED.md`](FINDINGS-TO-BE-REMOVED.md) for a curated list of features and code identified for removal, including:
- Guest mode
- Deprecated import shims
- Legacy credential encoding
- Placeholder modules
- Unimplemented features

---

## Cross-Project Data Flows

### Agent Execution (Local)

```
User Input
    ↓
[tinycua] CLI / TUI / REPL
    ↓
[tinycua-sdk] Agent.run()
    ↓
[tinycua-sdk] AgentExecutor._run_local()
    ↓
[tinycua-sdk] Runner → LLM API (OpenAI / LM Studio / Ollama)
    ↓
[tinycua-sdk] Tool calls dispatched via ToolRegistry
    ↓
Response → User
```

### Agent Execution (Remote / Backend)

```
User Input
    ↓
[tinycua] CLI / TUI
    ↓
[tinycua-sdk] Agent.deploy() → [tinycua-backend] POST /agents
    ↓
[tinycua-sdk] Agent.run() → [tinycua-backend] API
    ↓
[tinycua-backend] Sync service → [tinycua-runner] HTTP execution
    ↓
[tinycua-runner] LLM inference + tool execution
    ↓
Response → [tinycua-backend] → [tinycua-sdk] → User
```

### Session & Message Persistence

```
[tinycua-sdk] Session
    ↓
[tinycua-sdk] SessionStore (SQLite locally)
    ↓
[tinycua-backend] REST API (PostgreSQL remotely)
    ↓
[tinycua] Local session store + Remote sync engine
```

### Session Memory

```
[tinycua-sdk] MemorySession (session-scoped facade)
    ↓
[tinycua-sdk] LocalStorage / SessionStore
    ↓
SQLite memory table (session_id, memory_type, content)
```

---

## Documentation Conventions

Each documentation file follows this structure:

1. **Overview** — What this module/component does and where it fits
2. **Architecture** — How it connects to other parts of the system
3. **Detailed Module Breakdown** — File-by-file, class-by-class, function-by-function explanations
4. **Data Flows** — How data moves through the module
5. **Code Snippets** — Key implementation details
6. **Design Decisions** — Why things are built the way they are
7. **Security Considerations** — Where relevant

---

## Contributing to This Documentation

This documentation is a living document. As the code evolves:

1. Update the relevant section when modifying code.
2. Add new modules to the appropriate project section.
3. Update [`FINDINGS-TO-BE-REMOVED.md`](FINDINGS-TO-BE-REMOVED.md) when deprecated code is removed.
4. Keep cross-references up to date.

---

*Generated for TINYCUA branch: `enhance-documentation-and-code-cleanup`*
