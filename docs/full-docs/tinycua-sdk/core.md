# Core Module Documentation

The `core/` module provides the foundational infrastructure for the **tinycua-sdk**. It contains two critical subsystems:

1. **`registry.py`** — A thread-safe, centralized singleton for tool registration and dispatch.
2. **`config.py`** — A Pydantic-based immutable configuration system for the entire SDK.

**Package path:** `tinycua_sdk/core/`

---

## registry.py — Centralized Tool Registry

### Purpose

`registry.py` implements a **singleton registry** that acts as the single source of truth for all tools registered within the SDK. It guarantees thread-safe registration, lookup, and dispatch, ensuring that multiple threads or asynchronous contexts can interact with tools without race conditions.

---

### `ToolEntry`

```python
class ToolEntry:
    __slots__ = ("name", "toolset", "schema", "handler", "check_fn", "tool")
```

A lightweight, memory-efficient container for a single registered tool. Uses `__slots__` to reduce per-instance overhead.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Unique tool name. |
| `toolset` | `str \| None` | Optional group label (e.g., `"builtin"`, `"custom"`). |
| `schema` | `dict[str, Any]` | JSON-serializable schema dict for API calls. |
| `handler` | `Callable \| None` | The callable invoked when the tool is dispatched. |
| `check_fn` | `Callable \| None` | Optional availability check function. |
| `tool` | `Any` | Original `Tool` object (if applicable). |

#### `ToolEntry.__init__`

```python
def __init__(
    self,
    name: str,
    toolset: str | None,
    schema: dict[str, Any],
    handler: Callable | None,
    check_fn: Callable | None,
    tool: Any,
) -> None:
```

Initializes a new registry entry with the provided metadata and callables.

---

### `ToolRegistry`

```python
class ToolRegistry:
```

Centralized singleton registry for all tools. All operations are protected by an internal `threading.Lock`.

**Internal State:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `_instance` | `ClassVar[ToolRegistry \| None]` | Singleton instance holder. |
| `_tools` | `dict[str, ToolEntry]` | Map of tool names to `ToolEntry` objects. |
| `_lock` | `threading.Lock` | Mutex for thread-safe mutations. |

#### `ToolRegistry.__new__`

```python
def __new__(cls) -> "ToolRegistry"
```

Creates or returns the existing singleton instance. On first call, it initializes `_tools` as an empty dict and `_lock` as a new `threading.Lock`.

#### `ToolRegistry.create`

```python
@classmethod
def create(cls) -> "ToolRegistry"
```

Creates a **new, non-singleton** registry instance. Useful for test isolation or when you need a separate registry scope.

#### `ToolRegistry.create_for_test`

```python
@classmethod
def create_for_test(cls) -> "ToolRegistry"
```

Alias for `create()`. Explicitly intended for testing scenarios where a clean, isolated registry is required.

#### `ToolRegistry.register`

```python
def register(
    self,
    name: str,
    toolset: str | None = None,
    schema: dict[str, Any] | None = None,
    handler: Callable | None = None,
    check_fn: Callable | None = None,
    tool: Any | None = None,
) -> None
```

Registers a new tool. If a tool with the same `name` already exists, raises `ValueError`.

**Behavior:**
- Acquires `_lock` before mutation.
- Stores `schema or {}` (defaults to empty dict if `None`).

#### `ToolRegistry.deregister`

```python
def deregister(self, name: str) -> bool
```

Removes a tool by name. Returns `True` if the tool was found and removed, `False` otherwise.

#### `ToolRegistry.get`

```python
def get(self, name: str) -> ToolEntry | None
```

Retrieves a `ToolEntry` by name. Returns `None` if not found.

#### `ToolRegistry.get_definitions`

```python
def get_definitions(self, tool_names: list[str] | None = None) -> list[dict]
```

Returns a list of tool schemas.

- If `tool_names` is `None`, returns schemas for **all** registered tools.
- If `tool_names` is provided, returns schemas only for the requested names that exist in the registry.

#### `ToolRegistry.dispatch`

```python
def dispatch(self, name: str, args: dict[str, Any], **kwargs: Any) -> Any
```

Executes a tool's handler.

**Raises:**
- `KeyError` — if the tool is not registered.
- `RuntimeError` — if the tool has no handler (`handler is None`).

**Behavior:**
- Acquires `_lock` for the lookup.
- Calls `entry.handler(**args, **kwargs)` and returns the result.

#### `ToolRegistry.is_toolset_available`

```python
def is_toolset_available(self, toolset: str) -> bool
```

Returns `True` if **at least one** registered tool belongs to the given `toolset`.

#### `ToolRegistry.clear`

```python
def clear(self) -> None
```

Removes all tools from the registry. Typically used in test teardown to ensure isolation.

---

### How the Registry Works

1. **Singleton Pattern**  
   `ToolRegistry()` always returns the same instance within a process. This ensures that any part of the SDK or user code that registers or looks up tools sees a consistent view.

2. **Thread Safety**  
   Every mutating and lookup operation (`register`, `deregister`, `get`, `dispatch`, `clear`) wraps its access to `_tools` inside a `threading.Lock` context. This prevents race conditions during concurrent registration or dispatch.

3. **Test Isolation**  
   Because the singleton persists for the lifetime of the process, tests can pollute each other's state. Use `ToolRegistry.create_for_test()` (or `create()`) to obtain a fresh, isolated instance, or call `clear()` on the singleton during teardown.

4. **Dispatch Flow**  
   When the agent loop or an external caller wants to execute a tool, it calls `dispatch(name, args)`. The registry looks up the `ToolEntry`, verifies a handler exists, and invokes it with the provided arguments.

---

## config.py — SDK Configuration System

### Purpose

`config.py` defines the **immutable, validated configuration hierarchy** for the SDK. It is built on [Pydantic](https://docs.pydantic.dev/) `BaseModel` with `frozen=True`, meaning all config instances are read-only after creation. This prevents accidental mutation of global settings at runtime.

---

### `LLMConfig`

```python
class LLMConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str = "openai-compatible"
    model: str = "qwen/qwen3.5-9b"
    base_url: str = "http://localhost:1234/v1"
    api_key: SecretStr = SecretStr("")
    temperature: float = 1.0
```

Configuration for the LLM provider.

**Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `provider` | `"openai-compatible"` | Name of the LLM provider backend. |
| `model` | `"qwen/qwen3.5-9b"` | Model identifier string. |
| `base_url` | `"http://localhost:1234/v1"` | Base URL for the provider API. |
| `api_key` | `SecretStr("")` | API key wrapped in Pydantic `SecretStr` for safe logging. |
| `temperature` | `1.0` | Sampling temperature. |

---

### `MemoryConfig`

```python
class MemoryConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    database_url: str = "sqlite:///./tinycua.db"
    embedding_dimension: int = 1536
```

Configuration for memory and vector storage.

**Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `database_url` | `"sqlite:///./tinycua.db"` | Database connection string. |
| `embedding_dimension` | `1536` | Dimensionality of embedding vectors. |

---

### `SessionConfig`

```python
class SessionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_turns: int = 100
    summary_enabled: bool = True
```

Configuration for conversational session management.

**Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `max_turns` | `100` | Maximum number of turns before session reset/re-summary. |
| `summary_enabled` | `True` | Whether automatic session summarization is enabled. |

---

### `LoopConfig`

```python
class LoopConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str = "default"
    max_iterations: int = 5
```

Configuration for the agent execution loop.

**Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `type` | `"default"` | Loop strategy type identifier. |
| `max_iterations` | `5` | Hard cap on the number of loop iterations per request. |

---

### `SkillsConfig`

```python
class SkillsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    directories: list[str] = Field(
        default_factory=lambda: [
            os.path.expanduser("~/.tinycua/skills"),
            "./skills",
        ]
    )
    auto_load: bool = True
    auto_improve: bool = True
```

Configuration for the skills (custom tool) system.

**Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `directories` | `["~/.tinycua/skills", "./skills"]` | List of filesystem paths to scan for skill definitions. |
| `auto_load` | `True` | Whether to automatically load discovered skills on startup. |
| `auto_improve` | `True` | Whether the SDK is permitted to auto-improve skills. |

---

### `SDKConfig`

```python
class SDKConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    backend_url: str = "http://localhost:8000"
    environment: str = "dev"
```

Top-level immutable configuration object. Composes all subsystem configs plus global settings.

**Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `llm` | `LLMConfig()` | LLM provider settings. |
| `memory` | `MemoryConfig()` | Memory/storage settings. |
| `session` | `SessionConfig()` | Session management settings. |
| `loop` | `LoopConfig()` | Agent loop settings. |
| `skills` | `SkillsConfig()` | Skill system settings. |
| `backend_url` | `"http://localhost:8000"` | URL of the tinycua backend server. |
| `environment` | `"dev"` | Runtime environment identifier (e.g., `"dev"`, `"prod"`). |

#### `SDKConfig.get_skill_directories`

```python
def get_skill_directories(self) -> list[Path]
```

Converts `self.skills.directories` (list of strings) into `pathlib.Path` objects and returns them.

#### `SDKConfig.from_yaml`

```python
@classmethod
def from_yaml(cls, path: str | Path) -> "SDKConfig"
```

Loads and validates configuration from a YAML file.

**Raises:**
- `FileNotFoundError` — if the file does not exist.
- `yaml.YAMLError` — if the file contains invalid YAML.
- `pydantic.ValidationError` — if the loaded data fails Pydantic validation.

**Behavior:**
- Empty or missing YAML content is treated as an empty dict (`{}`), resulting in an all-defaults config.

#### `SDKConfig.from_env`

```python
@classmethod
def from_env(cls) -> "SDKConfig"
```

Builds a configuration by reading supported environment variables.

**Mapped variables:**

| Environment Variable | Target Field |
|----------------------|--------------|
| `TINYCUA_ENV` | `environment` |
| `TINYCUA_BACKEND_URL` | `backend_url` |
| `TINYCUA_API_KEY` | `llm.api_key` |
| `TINYCUA_PROVIDER` | `llm.provider` |
| `TINYCUA_MODEL` | `llm.model` |
| `TINYCUA_BASE_URL` | `llm.base_url` |
| `TINYCUA_DATABASE_URL` | `memory.database_url` |
| `TINYCUA_LOOP_TYPE` | `loop.type` |

Any variable that is not set is omitted, and the corresponding default value is used.

#### `SDKConfig.load`

```python
@classmethod
def load(cls, path: str | Path | None = None) -> "SDKConfig"
```

Convenience loader that applies the following priority:

1. **YAML file** — if `path` is provided, calls `from_yaml(path)`.
2. **Environment variables** — if `path` is `None`, calls `from_env()`.
3. **Defaults** — any fields not supplied by the chosen source fall back to their Pydantic default values.

---

### How `SDKConfig` Works

1. **Immutability**  
   Every config class sets `model_config = ConfigDict(frozen=True)`. Once an `SDKConfig` instance is created, its fields cannot be reassigned. This makes config objects safe to share across threads and prevents accidental runtime corruption.

2. **Validation**  
   Because the classes inherit from Pydantic `BaseModel`, all fields are type-checked at instantiation. Invalid types (e.g., a string where an int is expected) raise `pydantic.ValidationError` immediately.

3. **Secure Secrets**  
   The `api_key` field uses Pydantic's `SecretStr`. When the config is printed or logged, the key is masked as `**********` rather than leaking sensitive text.

4. **Hierarchical Loading**  
   The `load()` method provides a simple, opinionated resolution order: explicit YAML file beats environment variables, and both beat baked-in defaults. This allows developers to commit a base config to version control while overriding secrets or URLs locally via environment variables.

---

## Deprecation Warnings & Backward Compatibility

As of the current implementation, **no deprecation warnings or backward-compatibility shims are present** in `registry.py` or `config.py`. All classes and methods are the canonical versions. If future releases introduce breaking changes, they should be noted here.

---

## Summary

| File | Key Classes | Responsibility |
|------|-------------|--------------|
| `registry.py` | `ToolEntry`, `ToolRegistry` | Thread-safe tool registration, lookup, and dispatch. |
| `config.py` | `SDKConfig` (and nested configs) | Immutable, validated, hierarchical SDK configuration. |
