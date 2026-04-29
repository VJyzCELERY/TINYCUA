# Refactor Plan — Detailed Specification

This document contains the complete, actionable refactor plan for `tinycua-sdk`.  
Each section maps 1-to-1 to the high-level findings in the original analysis but now contains **concrete file operations**, **interface definitions**, **migration steps**, and **acceptance criteria**.

> **Legend for ID**
> - **H** — High Priority (blocks other work, data-loss risk, or architectural inconsistency)
> - **M** — Medium Priority (code-quality or developer-experience impact)
> - **L** — Low Priority (cosmetic, legacy naming, or nice-to-have)

---

## Design Principles

### 1. SDK Scope
`tinycua_sdk` is a **runnable, stateless framework** for building and executing AI agents. You can create an agent in one line and run it immediately. The SDK provides the building blocks (Agent, Tool, Skill, Config, Loop) but does not manage runtime state, persistence, or infrastructure.

**What the SDK provides:**
- **Agent execution**: `Agent`, `AgentExecutor`, agent loop logic. Fully runnable out of the box.
- **Tool framework**: `@tool` decorator, `Tool` dataclass, schema generation.
- **Skill framework**: `Skill` dataclass, skill registry, skill loader.
- **Configuration**: Pydantic-based config classes (`AgentConfig`, `SDKConfig`, `LLMModel`, etc.) for programmatic and file-based (YAML/JSON) agent creation.
- **Templates**: Pre-built agent templates (coder, researcher, assistant).

**What the SDK does NOT provide:**
- Session management, message history, or conversation state.
- Memory storage, snapshots, or retrieval.
- User profiling, personality modeling, or communication analysis.
- Database connections, stores, backends, or migration utilities.
- CLI, REPL, or command-line tools.
- HTTP clients for remote backends.
- Singleton registries or global caches.

### 2. SDK Statelessness
Program state — including which LLM is configured, which database is connected, which session is active, which tools are registered — is owned by the **consumer** (backend application or client script), not by the SDK.

- **No stores**: The SDK does not contain `*Store`, `*Manager`, or `*Backend` classes that hold database connections, file handles, HTTP clients, or cached state.
- **No singletons**: The SDK does not contain module-level caches, global registries, or singleton instances (e.g., no `ToolRegistry()` singleton, no `_default_store` globals).
- **No persistence logic**: The SDK never performs `INSERT`, `UPDATE`, `DELETE`, file writes, or HTTP POSTs on behalf of the consumer.
- **Fully-hydrated inputs**: The SDK accepts fully-hydrated configuration objects at call sites (`Agent(llm_model=my_llm)` rather than `Agent(llm_model="default")` with an internal database lookup).
- **Configuration-based creation**: The SDK supports creating agents, tools, and skills from YAML/JSON configuration files — this is stateless deserialization, not persistence.

### 3. Separation of Concerns
- `tinycua_sdk/` = pure framework (agent loop, tool decorator, skill loader, config schemas, templates).
- `tinycua_backend/` or host application = owns databases, connection pools, session management, memory systems, user modeling, stores, registries, environment config, multi-tenancy, and stateful services.

---

## 1. Session

### 1.1 Recommendation [H-01] — Remove Session from the SDK entirely

Session management (conversation state, message history, turn tracking) is **out of scope** for the SDK. The consumer (backend application) owns session lifecycle.

#### Files to delete

| File | Reason |
|------|--------|
| `session/session.py` | File-based session manager — stateful |
| `session/__init__.py` | Package init for deleted module |
| `utils/session.py` | Session utility wrappers — stateful |
| `storage/models.py` | `Session` / `Message` ORM models — belong in consumer |
| `storage/store.py` | `SessionStore` — stateful CRUD |

#### Step-by-step

1. **Delete the entire `session/` package**
   - `src/tinycua-sdk/tinycua_sdk/session/session.py`
   - `src/tinycua-sdk/tinycua_sdk/session/__init__.py`

2. **Delete `utils/session.py`**

3. **Remove `Session` / `Message` models** from `storage/models.py` (already covered in §2)

4. **Update `Agent`** so it no longer references sessions:
   - Remove `session_id` parameter from `Agent.__init__`
   - Remove `messages` list from `AgentExecutor` (consumer passes message history into `run()` if needed)
   - The agent loop receives `messages: list[dict]` as a parameter, not as internal state

#### Consumer-side example
The consumer manages sessions in its own codebase:
```python
# host_app/models/session.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    # ... consumer defines its own session schema

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # ... consumer defines its own message schema
```

```python
# host_app/agent_runner.py
from tinycua_sdk import Agent, LLMModel

async def run_agent(session_id: str, user_input: str, db):
    # Consumer loads message history from its own DB
    messages = db.query(Message).filter_by(session_id=session_id).all()
    message_dicts = [{"role": m.role, "content": m.content} for m in messages]
    
    agent = Agent(llm_model=LLMModel())
    response = await agent.run(user_input, messages=message_dicts)
    
    # Consumer saves new messages to its own DB
    db.add(Message(session_id=session_id, role="user", content=user_input))
    db.add(Message(session_id=session_id, role="assistant", content=response))
    db.commit()
```

#### Acceptance Criteria
- The `session/` package is deleted.
- `utils/session.py` is deleted.
- `Agent` does not hold message history as internal state.
- `Agent.run()` accepts `messages` as an optional parameter.

---

## 2. Storage

### 2.1 Philosophy

Because the SDK is stateless, **it does not contain stores, backends, connection managers, or migration utilities**.  
The SDK provides only:
1. **Data models** (SQLAlchemy ORM classes) so the consumer knows the schema.
2. **Pure functions** for logic that does not require I/O.

The consumer is responsible for:
- Creating database engines and connections.
- Managing migrations (Alembic, raw SQL, etc.).
- Implementing CRUD, caching, and remote syncing.

### 2.2 Current State

```
storage/
  __init__.py
  models.py        ← Session & Message (SQLAlchemy)
  store.py         ← SessionStore (SQLAlchemy CRUD) — stateful, must be deleted
  snapshot.py      ← MemorySnapshot / SnapshotManager (raw SQL) — stateful, must be deleted
  sqlite.py        ← LocalStorage (raw sqlite3) — stateful, must be deleted
  importer.py      ← Importer (works with LocalStorage) — stateful, must be deleted
  export.py        ← Exporter (works with LocalStorage) — stateful, must be deleted
```

### 2.3 Recommendation [H-02] — Delete the entire `storage/` package

All files in `storage/` are stateful and therefore out of scope for the SDK.

#### Files to delete
- `storage/__init__.py`
- `storage/models.py` → **delete** (`Session` / `Message` models belong in the consumer)
- `storage/store.py` → **delete** (consumer builds their own session store)
- `storage/snapshot.py` → **delete** (consumer builds their own snapshot logic)
- `storage/sqlite.py` → **delete** (consumer manages raw sqlite3 if needed)
- `storage/importer.py` → **delete** or rewrite as pure functions (see §2.5)
- `storage/export.py` → **delete** or rewrite as pure functions (see §2.5)

#### Target file layout (framework-only)

```
tinycua_sdk/
  agent/
    __init__.py
    agent.py           # Agent class
    config.py          # AgentConfig, AgentPolicy
    definition.py      # AgentDefinition
    executor.py        # AgentExecutor
    loop.py            # Loop logic
    llm_model.py       # LLMModel value object
    backend_kind.py    # BackendConfig value object
    templates.py       # Agent templates

  tools/
    __init__.py
    decorators.py      # @tool, Tool dataclass
    schema.py          # JSON-schema generation
    parser.py          # Source parsing
    resolver.py        # Dependency resolution
    mcp.py             # MCP integration
    cua/               # CUA helpers
    native/            # Built-in tools (memory_tools removed)
      __init__.py
      context_tools.py

  skills/
    __init__.py
    models.py          # Skill dataclass
    registry.py        # SkillRegistry (non-singleton)
    loader.py          # Skill loader from filesystem
    improver.py        # Skill improvement logic
    cache.py           # Skill cache (ephemeral, not persistent)

  core/
    __init__.py
    config.py          # SDKConfig
```

> There is **no** `storage/` directory, **no** `session/` directory, **no** `memory/` directory, **no** `modeling/` directory, **no** `clients/` directory, **no** `cli/` directory, **no** `utils/session.py`.

### 2.4 Recommendation [H-04] — Remove Memory from the SDK entirely

Memory management (short-term context, long-term facts, snapshots, embeddings) is **out of scope** for the SDK. The consumer (backend application) owns memory systems.

#### Files to delete

| File | Reason |
|------|--------|
| `memory/short_term.py` | In-memory `ShortTermMemory` — stateful |
| `memory/long_term.py` | File-based `LongTermMemory` — stateful |
| `memory/__init__.py` | Package init for deleted module |
| `memory/plugin.py` | Memory plugin system — stateful |
| `memory/compression.py` | Context compression — belongs in consumer |
| `memory/cache.py` | Memory cache — stateful |
| `storage/snapshot.py` | Snapshot manager — stateful |

#### Step-by-step

1. **Delete the entire `memory/` package**

2. **Delete `storage/snapshot.py`**

3. **Update `Agent`** so it no longer references memory:
   - Remove `short_term_memory` and `long_term_memory` parameters from `Agent.__init__`
   - Remove any memory-related imports from `agent/executor.py`
   - The agent loop operates on the `messages` list passed in by the consumer; it does not fetch or store memory

#### Consumer-side example
The consumer manages memory in its own codebase:
```python
# host_app/memory.py
from typing import Any

class MemoryManager:
    """Consumer's own memory implementation."""
    def remember(self, content: str) -> None: ...
    def recall(self, query: str) -> list[str]: ...
```

```python
# host_app/agent_runner.py
from tinycua_sdk import Agent, LLMModel

async def run_agent(user_input: str, messages: list[dict], memory: MemoryManager):
    # Consumer injects relevant memory into the context
    facts = memory.recall(user_input)
    system_prompt = "You are a helpful assistant.\n\nRelevant facts:\n" + "\n".join(facts)
    
    agent = Agent(
        llm_model=LLMModel(system_prompt=system_prompt),
        instructions="Answer based on the relevant facts provided.",
    )
    response = await agent.run(user_input, messages=messages)
    
    # Consumer decides what to remember
    memory.remember(f"User asked: {user_input}. Agent replied: {response}")
```

#### Acceptance Criteria
- The `memory/` package is deleted.
- `storage/snapshot.py` is deleted.
- `Agent` does not reference memory in any way.

### 2.5 Recommendation [M-01] — Remove import / export modules

Backup, restore, and data migration are **consumer concerns**. The SDK does not handle import/export of database dumps.

#### Files to delete
- `storage/importer.py`
- `storage/export.py`

#### Consumer-side example
The consumer implements its own backup logic:
```python
# host_app/backup.py
import json

def export_agents(agents: list[Agent]) -> str:
    data = [a.to_config() for a in agents]
    return json.dumps({"version": "1.0.0", "agents": data})

def import_agents(data: str) -> list[Agent]:
    parsed = json.loads(data)
    return [Agent.from_config(c) for c in parsed["agents"]]
```

---

## 3. Tools

### 3.1 Current State

```
tools/
  decorators.py      # Tool dataclass + @tool decorator
  schema.py          # JSON-schema generation
  parser.py          # Source parsing
  resolver.py        # Dependency resolution
  memory.py          # MemoryBackend (generic KV) — stateful, must be deleted
  memory_tools.py    # @tool decorated remember/recall/forget/etc. — depends on memory
  context_tools.py   # @tool decorated context helpers
  mcp.py             # MCP integration
  cua/               # CUA sub-package
```

### 3.2 Recommendation [H-05] — Tool framework (no storage)

The SDK provides the **Tool dataclass and `@tool` decorator** so consumers can define tools.  
The SDK does NOT provide tool storage, registration persistence, or backend clients.

#### What stays
- `decorators.py` — `@tool` decorator, `Tool` dataclass
- `schema.py` — JSON-schema generation
- `parser.py` — Source parsing
- `resolver.py` — Dependency resolution (pure functions)
- `mcp.py` — MCP integration
- `cua/` — CUA helpers

#### What is deleted
- `tools/memory.py` — `MemoryBackend` hierarchy (stateful KV store)
- `tools/memory_tools.py` — Memory tools depend on the memory module, which is removed
- `tools/store.py` — Does not exist yet, do not create
- `tools/backend.py` — Do not create
- `tools/models.py` — Do not create (no ORM models for tools in SDK)

#### `Tool` dataclass (existing, keep as-is)

```python
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    _fn: Callable | None = field(default=None, repr=False)
    _source: str | None = field(default=None, repr=False)
    _external_dependencies: list[str] = field(default_factory=list)
    _tool_dependencies: list[dict[str, Any]] = field(default_factory=list)
    _version: str | None = field(default=None, repr=False)

    def to_config(self) -> dict[str, Any]: ...
    def to_bundle(self) -> dict[str, Any]: ...
    def invoke(self, **kwargs: Any) -> Any: ...
```

> `to_bundle()` produces a serialization-friendly dict. The **consumer** decides whether to store it in a database, send it over HTTP, or write it to a file.

#### Future-proofing: dependency resolver (deferred to future PR)

The `Tool` dataclass already reserves `_external_dependencies` and `_tool_dependencies`.  
When the resolver is implemented in the **consumer**, it can:
1. Parse `@tool(dependencies=[...])` from the bundle.
2. Create isolated `.venv` environments per tool.
3. Activate the tool's `.venv` before `invoke()`.

**Do NOT implement the resolver now** — just ensure the `Tool` schema supports it.

### 3.3 Recommendation [H-06] — Delete memory tools

`memory_tools.py` and `memory.py` are deleted because memory management is out of scope.

1. Delete `tools/memory.py`
2. Delete `tools/memory_tools.py`
3. If `context_tools.py` depends on session/memory state, evaluate whether it should also be deleted or moved to `tools/native/` as a generic context utility.

### 3.4 Recommendation [M-01] — Restructure tool module layout

```
tools/
  __init__.py
  decorators.py          # SDK primitive: @tool, Tool class
  schema.py              # SDK primitive: JSON-schema helpers
  parser.py              # SDK primitive: source parsing
  resolver.py            # SDK primitive: dependency resolution
  mcp.py                 # SDK primitive: MCP integration
  cua/                   # SDK primitive: CUA helpers
  native/                # Built-in tools shipped with the SDK
    __init__.py
    context_tools.py     # Generic context utilities (no session/memory dependency)
```

Rules:
- `tools/` root = SDK infrastructure (decorator, schema, parsing, resolution).
- `tools/native/` = generic tool implementations (e.g., file I/O, math) that do not depend on session, memory, or external state.
- Third-party / user tools live outside the package (e.g., `./my_tools/`).
- **No storage, no backends, no ORM models in `tools/`**.

---

## 4. Skills

### 4.1 Current State

- `skills/backend.py` defines its own `SkillBackend` / `LocalSkillBackend` / `RemoteSkillBackend` / `HybridSkillBackend` hierarchy — **parallel invention** of the same pattern found in `tools/memory.py`.
- `skills/tools.py` defines `CallableTool`, a wrapper around `@tool` decorated functions, plus `create_skills_list_tool` and `create_skill_view_tool`. These are **skill-native tools** and should live in `tools/native/`.
- `skills/models.py` `Skill.path` is a `Path | None`. It is unclear whether this supports MinIO/S3 URIs.

### 4.2 Recommendation [M-02] — Delete skill backend

Skill storage is the consumer's responsibility. The SDK only loads skills from the filesystem or configuration dicts.

1. Delete `skills/backend.py` entirely.
2. Keep `skills/models.py` as a **Pydantic dataclass** (not SQLAlchemy ORM) for skill definition:
   ```python
   from dataclasses import dataclass, field
   from datetime import datetime
   from typing import Any

   @dataclass
   class Skill:
       name: str
       description: str = ""
       category: str = "general"
       instructions: str = ""
       tools: list[str] = field(default_factory=list)
       dependencies: list[str] = field(default_factory=list)
       source: str | None = None   # file path or URI
       metadata: dict[str, Any] = field(default_factory=dict)
       is_active: bool = True
       version: str = "1.0.0"
   ```
3. `SkillRegistry` must be **non-singleton**, instantiated by the consumer. No filesystem I/O:
   ```python
   # BEFORE (singleton)
   registry = SkillRegistry()  # implicit global state

   # AFTER (explicit instance)
   registry = SkillRegistry()

   # Consumer decides how to obtain skill definitions
   with open("./skills/coder.md") as f:
       coder = Skill.load(f.read())
   registry.register(coder)

   # Or inline
   researcher = Skill.load("""
   ---
   name: researcher
   ---
   # Researcher
   ## Instructions
   Research topics thoroughly.
   """)
   registry.register(researcher)

   agent = Agent(skills=registry.list_skills())
   ```

### 4.3 Recommendation [H-07] — Skill tools should use the canonical tool system

1. Move `skills/tools.py` → `tools/native/skills_tools.py`.
2. Remove `CallableTool` wrapper **unless** there is a documented reason it cannot be replaced by the standard `Tool` class.
   - **Analysis**: `CallableTool` exists solely to convert positional args to keyword args via `inspect.signature`. The standard `Tool.invoke()` already accepts `**kwargs`. `CallableTool` is therefore redundant.
   - **Action**: Delete `CallableTool`. Replace `create_skills_list_tool(registry)` with a plain `@tool` function that captures `registry` via closure or accepts it as a parameter.
3. Update `skills/registry.py` so that `SkillRegistry` no longer imports from `skills.tools.CallableTool`.

### 4.4 Recommendation [L-01] — Skill source path must support MinIO

Change `Skill.path: Path | None` to `Skill.source: str | None` where the string can be:
- A local filesystem path (`file:///home/user/skills/...` or raw path for backward compat)
- A MinIO/S3 URI (`s3://bucket/skills/...`)
- A `memory://` reference for inline content

Update `skills/loader.py` to delegate to a `SourceResolver` that handles the protocol prefix.

---

## 5. CLI

### 5.1 Recommendation [H-08] — Remove CLI from SDK

The CLI is a **consumer** of the SDK, not part of it.

#### Files to delete

- `src/tinycua-sdk/tinycua_sdk/cli/__init__.py`
- `src/tinycua-sdk/tinycua_sdk/cli/main.py`
- `src/tinycua-sdk/tinycua_sdk/cli/repl.py`
- `src/tinycua-sdk/tinycua_sdk/cli/agent_commands.py`

#### If a CLI is still needed short-term

Move it to a **separate package** (e.g., `tinycua-cli/` at repo root or a new repository).  
The new package adds `tinycua-sdk` as a dependency in `pyproject.toml`.

#### Acceptance Criteria
- `rg "cli/" src/tinycua-sdk/tinycua_sdk/` returns 0 hits.
- `pyproject.toml` entry-point `console_scripts` is removed (or points to the new package).

---

## 6. Core

### 6.1 Recommendation [L-02] — Replace hard-coded LMStudio defaults

In `core/config.py`:

```python
# BEFORE
provider: str = "lmstudio"
base_url: str = "http://localhost:1234"

# AFTER
provider: str = "openai-compatible"
base_url: str = "http://localhost:1234/v1"
```

Also update any docstrings or comments that mention `lmstudio` as a first-class provider.  
`lmstudio` is still usable as a *value* for `provider`, but the default should be generic.

### 6.2 Recommendation [H-09] — Remove `ToolRegistry` singleton

The `ToolRegistry` singleton (`core/registry.py`) is **global mutable state** and violates SDK statelessness.

#### Decision
**Delete `core/registry.py` entirely.**

#### Rationale
- `Agent` already holds its own `list[Tool]` — it does not need a global registry.
- If the consumer wants a registry, it builds its own in its own codebase.
- The `@tool` decorator should return a `Tool` instance directly, not register it into a global singleton.

#### Migration
```python
# BEFORE (global singleton)
from tinycua_sdk.core.registry import ToolRegistry

@tool
def my_tool(): ...

registry = ToolRegistry()
registry.register("my_tool", schema=..., handler=my_tool.invoke)

# AFTER (explicit, stateless)
from tinycua_sdk.tools.decorators import tool

my_tool = tool(lambda: ...)  # returns Tool instance

agent = Agent(tools=[my_tool])  # explicit composition
```

#### Files to delete
- `core/registry.py`
- Any code that imports from `core.registry`

### 6.3 Recommendation [L-03] — Remove `environment: str = "dev"` from `SDKConfig`

Unless a grep proves it is consumed somewhere:

```bash
rg "\.environment" src/
rg "TINYCUA_ENV" src/
```

If the only usage is in `SDKConfig.from_env()`, remove the field and the env-var mapping.  
Environment distinction (dev/staging/prod) should live in the **host application** or deployment config, not the SDK.

### 6.4 Recommendation [M-03] — Refactor `SDKConfig` to framework-only concerns

Current `SDKConfig` contains stateful concerns (`memory`, `session`) that are out of scope. Refactor to only include framework configuration.

#### New `SDKConfig` structure

```python
class LLMConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: str = "openai-compatible"
    model: str = "gpt-4o-mini"
    base_url: str = "http://localhost:1234/v1"
    api_key: SecretStr = SecretStr("")
    temperature: float = 1.0

class LoopConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: str = "default"
    max_iterations: int = 5

class SkillsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    directories: list[str] = Field(default_factory=lambda: ["./skills"])
    auto_load: bool = True

class SDKConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    backend_url: str = "http://localhost:8000"
```

#### Removed
- `memory` — out of scope
- `session` — out of scope
- `environment` — see §6.3

#### Note on context/security configs
Context compression, security permissions, and approval modes are **consumer concerns**. The SDK's `Agent` accepts `instructions` as a string; the consumer decides how to construct it (including any context window management or permission checks). The `LLMModel` carries the `system_prompt` for model-specific behavior tuning.

---

## 7. Agent

### 7.1 Current State

`Agent` (in `agent/agent.py`) inherits `AgentExecutor` → `AgentDefinition`.  
It currently stores:
- `model: str`
- `provider: str`
- `base_url: str | None`
- `api_key: str | None`
- `mode: str`
- `backend_url`, `backend_api_key`, `backend_headers`
- `short_term_memory`, `long_term_memory`
- `planning_prompt`

### 7.2 Recommendation [L-04] — Introduce `LLMModel` as a pure configuration object

`LLMModel` is a **value object** (no database, no store, no internal state). It carries all metadata required to call an LLM endpoint. The consumer decides how to obtain it — from env vars, a database, a YAML file, or hard-coded constants.

```python
# agent/llm_model.py
from pydantic import BaseModel, SecretStr

class LLMModel(BaseModel):
    """Immutable LLM endpoint configuration."""
    model_config = ConfigDict(frozen=True)

    provider: str = "openai-compatible"
    model_name: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: SecretStr = SecretStr("")
    max_context: int = 128_000
    temperature: float = 1.0
    system_prompt: str = "You are a helpful assistant."
```

**Why `system_prompt` lives on `LLMModel`:**
- Different models interpret instructions differently. A system prompt that works well for GPT-4 may not work well for Claude or a local Qwen model.
- `LLMModel.system_prompt` is the **model-specific behavior tuning** (how to talk to THIS model).
- `Agent.instructions` is the **task-specific directive** (what THIS agent should do).
- This separation allows swapping models without rewriting behavior prompts, and vice versa.
- At runtime the agent combines both: `LLMModel.system_prompt` + `Agent.instructions` → final prompt.

**Rules:**
- `LLMModel` must not perform I/O, file reads, or database lookups.
- `LLMModel` must not have a `.save()` or `.load()` method.
- If the consumer wants persistence, it builds its own `LLMModelStore` **outside** the SDK.

### 7.3 Recommendation [H-10] — Decouple LLM model from Agent

Agent should not own the model configuration; it should receive a fully-hydrated `LLMModel` object from the consumer.  
This keeps the SDK stateless: the SDK does not know or care whether the model config came from a database, an env var, or a hard-coded constant.

#### Step-by-step

1. Keep `LLMModel` as the pure value object defined in §7.2.  
   **Do NOT** create `agent/llm_store.py`, `LLMModelStore`, or an `LLMModelRecord` ORM model inside the SDK.

2. Change `Agent` constructor to accept `LLMModel` directly:
   ```python
   # BEFORE
   Agent(model="gpt-4o-mini", provider="openai", base_url=..., api_key=...)

   # AFTER
   Agent(llm_model: LLMModel = LLMModel())
   ```

3. Remove the old `model`, `provider`, `base_url`, `api_key` parameters from `Agent`, `AgentExecutor`, `AgentDefinition`, and `AgentConfig`.

4. Update `AgentDefinition` to expose the `LLMModel` properties through convenience accessors (optional):
   ```python
   @property
   def model(self) -> str:
       return self.config.llm_model.model_name

   @property
   def provider(self) -> str:
       return self.config.llm_model.provider
   ```

#### Consumer-side example (outside the SDK)

If the backend wants to store LLM configs in a database, it does so in its own codebase:

```python
# host_app/stores/llm_store.py  (NOT in tinycua_sdk)
class LLMModelStore:
    def get(self, alias: str) -> LLMModel:
        row = db.query(LLMConfigTable).filter_by(alias=alias).first()
        return LLMModel(
            provider=row.provider,
            model_name=row.model_name,
            base_url=row.base_url,
            api_key=row.api_key,
        )

# Usage inside the host application
llm = LLMModelStore().get("fast")
agent = Agent(llm_model=llm)
```

### 7.4 Recommendation [M-04] — Remove memory and session references

1. Delete `memory/short_term.py` and `memory/long_term.py` (see §2.4).
2. Remove `short_term_memory` and `long_term_memory` parameters from `Agent.__init__`.
3. Remove `session_id` parameter from `Agent.__init__`.
4. `Agent.run()` accepts an optional `messages` parameter (list of dicts) representing the conversation history. The consumer is responsible for loading and saving message history.

### 7.5 Recommendation [M-05] — Remove planning prompt and system_prompt from Agent

1. Delete `planning_prompt` parameter from `Agent`, `AgentExecutor`, `AgentDefinition`, `AgentConfig`.
2. Delete `system_prompt` parameter from `Agent`, `AgentExecutor`, `AgentDefinition`, `AgentConfig`.
   - System prompt now lives on `LLMModel` (see §7.2).
   - `Agent` retains `instructions` for task-specific directives.
3. Remove any reference in `agent/templates.py`.
4. The agent loop constructs the prompt from:
   - `llm_model.system_prompt` (model-specific behavior tuning)
   - `agent.instructions` (task-specific directive)
   - `user_input` (runtime query)

### 7.6 Recommendation [M-06] — Replace direct backend attributes with `BackendKind`

```python
# agent/backend_kind.py
from enum import Enum

class BackendKind(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"

class BackendConfig(BaseModel):
    kind: BackendKind = BackendKind.LOCAL
    url: str | None = None
    api_key: SecretStr = SecretStr("")
    headers: dict[str, str] = Field(default_factory=dict)
```

Changes to `Agent`:
- Remove `mode`, `backend_url`, `backend_api_key`, `backend_headers`.
- Add `backend: BackendConfig = Field(default_factory=BackendConfig)`.
- `Agent.is_deployed` → `agent.backend.kind == BackendKind.REMOTE`.
- `AgentConfig` stores `backend` as a dict; `AgentDefinition` hydrates it.

#### Streamlining consideration

The document notes: *“Agent should remain only for agent as minimal as possible such as list of tools, skills, loop etc.”*

After the above changes, `Agent` is a fully runnable, stateless object:

```python
class Agent(AgentExecutor):
    def __init__(
        self,
        name: str = "assistant",
        instructions: str = "",
        llm_model: LLMModel = LLMModel(),
        tools: list[Tool] | None = None,
        skills: list[str] | None = None,
        policy: AgentPolicy | None = None,
        backend: BackendConfig | None = None,
        sub_agents: list[Agent] | None = None,
        max_depth: int = 3,
        loop: Any = None,
        strip_thinking: bool | list[str] | None = None,
    ):
        ...

    # --- Mutation (still stateless; mutates this instance only) ---
    def add_tools(self, tools: Tool | list[Tool]) -> None: ...
    def add_skills(self, skills: Skill | list[Skill]) -> None: ...

    # --- Configuration serialization ---
    def to_config(self) -> dict[str, Any]: ...
    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Agent": ...

    # --- Execution ---
    async def run(
        self,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        instructions: str | None = None,
        stream: bool = False,
        trace: bool = False,
        verbose: bool = False,
    ) -> str | AsyncIterator[str]:
        """
        Run the agent with a user query.

        Args:
            query: The user input / task.
            messages: Optional conversation history (consumer-managed).
            instructions: Optional extra instructions for this turn.
            stream: If True, return an async iterator of text chunks.
            trace: If True, emit trace events.
            verbose: If True, emit verbose logging.
        """
        ...
```

#### Usage examples

**Basic usage:**
```python
from tinycua_sdk import Agent, LLMModel, Tool, tool

@tool
def search(query: str) -> str:
    return f"Results for {query}"

@tool
def summarize(text: str) -> str:
    return f"Summary: {text[:100]}..."

agent = Agent(
    llm_model=LLMModel(
        base_url="http://localhost:1234/v1",
        model_name="qwen3.5-9b",
        system_prompt="You are a research assistant.",
    ),
    instructions="Answer questions concisely using available tools.",
)

# Add a single tool
agent.add_tools(search)

# Add multiple tools
agent.add_tools([search, summarize])

response = await agent.run("What is quantum computing?")
print(response)
```

**With config file:**
```python
# agent.yaml
name: researcher
instructions: Answer questions concisely using available tools.
llm_model:
  provider: openai-compatible
  model_name: qwen3.5-9b
  base_url: http://localhost:1234/v1
  system_prompt: You are a research assistant.
tools:
  - search
  - summarize

# main.py
agent = Agent.from_config("agent.yaml")
response = await agent.run("Explain quantum computing")
```

**Streaming:**
```python
async for chunk in await agent.run("Tell me a story", stream=True):
    print(chunk, end="")
```

- `llm_model` is a pure value object passed in by the consumer.
- `backend` is a pure value object describing where the agent should run (local vs remote).
- `messages` is an optional conversation history passed in by the consumer.
- **No internal state**: `Agent` does not remember previous runs, sessions, or memory. Each `run()` is independent unless the consumer passes `messages`.

---

## 8. Codebase Overall

### 8.1 Recommendation [H-11] — Configuration-based loading (stateless)

The SDK supports creating agents, tools, and skills from YAML/JSON configuration files. This is **stateless deserialization** — the SDK reads a file and returns a fully-hydrated object. It does not cache, store, or manage the object lifecycle.

#### Pattern

```python
# agent/config.py
class AgentConfig:
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig": ...
    @classmethod
    def from_json(cls, path: str | Path) -> "AgentConfig": ...
    @classmethod
    def from_yaml(cls, path: str | Path) -> "AgentConfig": ...
    def to_dict(self) -> dict[str, Any]: ...
    def to_json(self, path: str | Path) -> None: ...
```

#### What the SDK provides

| Module | Config class | Loading mechanism |
|--------|--------------|-------------------|
| `agent` | `AgentConfig` | `from_dict()`, `from_json()`, `from_yaml()` |
| `tools` | `Tool` | `from_config()` (deserialize from dict) |
| `skills` | `Skill` | `from_dict()` (deserialize from dict) |
| `llm` | `LLMModel` | Direct instantiation (pure value object) |

#### What the SDK does NOT provide
- No `*Store` classes.
- No `load_from_db()`, `save_to_db()`, or `register()` methods.
- No singleton registries.

#### Consumer-side persistence
The consumer decides how to persist and load configurations:
```python
# host_app/stores.py
class AgentStore:
    def save(self, agent: Agent) -> None:
        config = agent.to_config()
        db.execute("INSERT INTO agents (config_json) VALUES (?)", [json.dumps(config)])
    
    def load(self, agent_id: str) -> Agent:
        row = db.execute("SELECT config_json FROM agents WHERE id = ?", [agent_id]).fetchone()
        config = AgentConfig.from_dict(json.loads(row["config_json"]))
        return Agent.from_config(config)
```

---

## 9. Modeling

### 9.1 Recommendation [M-07] — Remove Modeling from the SDK entirely

User modeling, profiling, and personality analysis are **out of scope** for the SDK. These are consumer concerns.

#### Files to delete

| File | Reason |
|------|--------|
| `modeling/__init__.py` | Package init |
| `modeling/user.py` | `UserModel`, `UserPreference`, `UserGoal` — consumer concern |
| `modeling/profiler.py` | `CommunicationProfiler` — consumer concern |
| `modeling/personality.py` | `Personality` — consumer concern |

#### Consumer-side example
The consumer implements user modeling in its own codebase:
```python
# host_app/modeling.py
class UserProfile:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.preferences = {}

# host_app/agent_runner.py
from tinycua_sdk import Agent, LLMModel

async def run_agent(user_id: str, user_input: str):
    profile = db.load_user_profile(user_id)
    system_prompt = f"User preferences: {profile.preferences}"
    
    agent = Agent(
        llm_model=LLMModel(system_prompt=system_prompt),
        instructions="Consider the user's preferences when answering.",
    )
    return await agent.run(user_input)
```

---

## 10. Client

### 10.1 Recommendation [H-12] — Remove `clients/` entirely

HTTP clients, backend communication, and remote orchestration are **consumer concerns**. The SDK is a local framework; the consumer decides how to communicate with remote backends.

#### Files to delete

| File | Reason |
|------|--------|
| `clients/__init__.py` | Package init |
| `clients/backend.py` | HTTP client — consumer concern |
| `clients/client.py` | `ResponsesClient` — consumer concern |
| `clients/protocol.py` | Protocol definitions — consumer concern |
| `clients/agent_client.py` | `AgentClient` — consumer concern |

#### Consumer-side example
The consumer implements its own backend client:
```python
# host_app/client.py
import httpx

class BackendClient:
    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key

    async def execute(self, agent_id: str, messages: list[dict]) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/agents/{agent_id}/run",
                json={"messages": messages},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            return response.json()["content"]
```

```python
# host_app/agent_runner.py
from tinycua_sdk import Agent, LLMModel, BackendConfig, BackendKind

async def run_remote(agent_id: str, user_input: str, backend_client: BackendClient):
    # Consumer decides whether to run local or remote
    agent = Agent(
        llm_model=LLMModel(),
        backend=BackendConfig(kind=BackendKind.REMOTE),
    )
    # Consumer handles remote execution via its own client
    return await backend_client.execute(agent_id, [{"role": "user", "content": user_input}])
```

---

## Appendix A — Migration Order (Suggested Sprint Plan)

| Sprint | Focus | Tickets |
|--------|-------|---------|
| **1** | Foundations | H-01 (remove session), H-08 (remove CLI), H-12 (remove clients) |
| **2** | Remove stateful modules | H-02 (delete storage/), H-04 (remove memory/), M-07 (remove modeling/), delete `sqlite.py` |
| **3** | Tool & Skill framework cleanup | H-05 (tool framework only), H-06 (delete memory tools), H-07 (skill tools), M-02 (skill backend removal) |
| **4** | Agent simplification | H-10 (LLMModel), M-04 (remove memory/session refs), M-05 (remove planning), M-06 (BackendKind) |
| **5** | Core cleanup | L-02 (lmstudio), H-09 (delete registry singleton), L-03 (env), M-03 (refactor config) |
| **6** | Config & loading | H-11 (config-based loading), validation, documentation |

---

## Appendix B — Acceptance Criteria Checklist

### Deleted modules
- [ ] `session/` package deleted entirely.
- [ ] `memory/` package deleted entirely.
- [ ] `modeling/` package deleted entirely.
- [ ] `storage/` package deleted entirely.
- [ ] `clients/` package deleted entirely.
- [ ] `cli/` package deleted entirely.
- [ ] `utils/session.py` deleted.
- [ ] `core/registry.py` deleted (ToolRegistry singleton removed).
- [ ] `tools/memory.py` deleted.
- [ ] `tools/memory_tools.py` deleted.
- [ ] `skills/backend.py` deleted.

### Refactored modules
- [ ] `Agent` constructor accepts only: `name`, `instructions`, `llm_model`, `tools`, `skills`, `policy`, `backend`, `sub_agents`, `max_depth`, `loop`, `strip_thinking`.
- [ ] `Agent.add_tools(tool)` accepts a single tool; `Agent.add_tools([tool1, tool2])` accepts a list.
- [ ] `Agent.add_skills(skill)` accepts a single skill; `Agent.add_skills([skill1, skill2])` accepts a list.
- [ ] `Agent.from_config()` classmethod works for YAML/JSON config loading.
- [ ] `Agent.run(query=..., stream=...)` works and returns string or async iterator.
- [ ] `Agent.run()` accepts `messages` as an optional parameter; no internal message history state.
- [ ] `Agent` does not reference session, memory, planning prompt, or system_prompt.
- [ ] `SDKConfig` contains only: `llm`, `loop`, `skills`, `backend_url`.
- [ ] `ToolRegistry` is deleted; `@tool` decorator returns a `Tool` instance directly.
- [ ] `SkillRegistry` is non-singleton, instantiated explicitly by the consumer.
- [ ] All configuration classes (`AgentConfig`, `SDKConfig`, `LLMModel`, `BackendConfig`) support `from_dict()` / `to_dict()` for stateless deserialization.
- [ ] `pytest` suite passes ≥ 90 % of tests (many legacy tests will be deleted along with the modules they test).

---

*End of document*
