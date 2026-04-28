# Agent Module Documentation

The agent module provides the core agent functionality for TinyCUA, including agent creation, lifecycle management (deploy, delete, load), and tool definitions.

---

## Module Structure

```
agent/
├── __init__.py          # Exports create_default_agent and AgentLifecycle
├── default_agent.py     # Factory for creating pre-configured agents
├── lifecycle.py         # Deploy, delete, load operations with backend
└── tools/               # Agent tools
    ├── __init__.py
    ├── context_tools.py # Session context retrieval tools
    ├── memory_tools.py  # Key-value memory tools
    └── cua/             # Computer-use automation tools
        ├── __init__.py
        ├── keyboard.py  # Keyboard input automation
        ├── mouse.py     # Mouse control automation
        └── screen_capture.py # Screen capture
```

---

## `agent/__init__.py`

```python
from tinycua.agent.default_agent import create_default_agent
from tinycua.agent.lifecycle import AgentLifecycle

__all__ = ["AgentLifecycle", "create_default_agent"]
```

This module exposes the two primary public APIs: creating a default agent and managing its lifecycle with a backend.

---

## `agent/default_agent.py`

### Purpose

Factory module that creates a pre-configured agent ready for local execution (primarily with Ollama).

### `create_default_agent()` Function

```python
def create_default_agent(
    config: SDKConfig | None = None,
    tools: list[Tool] | None = None,
) -> Agent:
```

**Parameters:**
- `config` — Optional `SDKConfig`. If `None`, loads from `UserConfig.load()` or falls back to `SDKConfig()` defaults.
- `tools` — Optional list of tools. If `None`, includes memory and context tools by default.

**Configuration loading logic:**
```python
if config is None:
    try:
        from tinycua.config.user_config import UserConfig
        config = UserConfig.load()
    except (OSError, ValueError, ImportError):
        from tinycua_sdk.core.config import SDKConfig
        config = SDKConfig()
```

Tries to load user config from `~/.tinycua/config.yaml`. If that fails (file missing, corrupted, or import error), falls back to SDK defaults.

**Default tools:**

When no tools are provided, the agent gets 8 built-in tools:

| Tool | Source Module | Purpose |
|------|--------------|---------|
| `remember` | `memory_tools` | Store a key-value pair |
| `recall` | `memory_tools` | Retrieve a value by key |
| `forget` | `memory_tools` | Delete a key |
| `list_memory` | `memory_tools` | List all memory keys |
| `clear_memory` | `memory_tools` | Clear all memory |
| `search_context_grep` | `context_tools` | Text search in session context |
| `get_context_summary` | `context_tools` | Get session summary |
| `get_recent_turns` | `context_tools` | Get recent conversation turns |

**Policy:**
```python
policy = AgentPolicy(max_tool_calls=10, parallel_tool_calls=True)
```

- `max_tool_calls=10` — Limits the agent to 10 tool calls per turn (prevents infinite loops)
- `parallel_tool_calls=True` — Allows the LLM to request multiple tools in parallel

**Agent creation:**
```python
agent = Agent(
    name="assistant",
    system_prompt=DEFAULT_SYSTEM_PROMPT,  # "You are a helpful assistant."
    model=config.llm.model,
    provider=config.llm.provider,
    base_url=config.llm.base_url,
    api_key=config.llm.api_key.get_secret_value() if config.llm.api_key else None,
    tools=tools,
    policy=policy,
    mode="local",
)
```

**Why `mode="local"`?** The agent starts in local mode. It can be switched to "deployed" mode via `AgentLifecycle`.

---

## `agent/lifecycle.py`

### Purpose

Manages agent lifecycle operations with a remote backend: deploy, delete, and load.

### `AgentLifecycle` Class

```python
class AgentLifecycle:
    def __init__(
        self,
        agent: Agent,
        backend_url: str | None = None,
        backend_api_key: str | None = None,
        backend_headers: dict[str, str] | None = None,
    ):
```

**Parameters:**
- `agent` — The `Agent` instance to manage
- `backend_url` — Optional backend URL (overrides agent config)
- `backend_api_key` — Optional API key
- `backend_headers` — Optional custom headers (for auth, multi-tenancy)

**Backend config priority:**
```
1. Constructor arguments (highest priority)
2. Agent config (agent.config.backend_url, etc.)
3. SDKConfig.load() global config
```

### `_get_client()` — Cached Client

```python
def _get_client(self) -> BackendClient:
    if self._client is None:
        backend_url, backend_api_key, backend_headers = self._get_backend_config()
        self._client = BackendClient(...)
    return self._client
```

The client is lazily created and cached. Call `close()` to clean up.

### `close()`

```python
async def close(self) -> None:
    if self._client is not None:
        await self._client.close()
        self._client = None
```

**Important:** Always call `close()` when done to avoid leaking HTTP connections.

### `_get_backend_config()`

Resolves backend configuration with priority:
```python
backend_url = (
    self._backend_url
    or self.agent.config.backend_url
    or config.backend_url
)
api_key = (
    self._backend_api_key
    or self.agent.config.backend_api_key
    or config.llm.api_key.get_secret_value()
    if config.llm.api_key
    else None
)
headers = self._backend_headers or self.agent.config.backend_headers
```

### `deploy()` — Deploy Agent to Backend

```python
async def deploy(self) -> dict[str, Any]:
```

**This is the most complex method in the module.** It:

1. **Analyzes tool dependencies:**
   ```python
   from tinycua_sdk.tools.resolver import (
       analyze_source, compute_version, detect_circular,
       find_internal_calls, topological_sort,
   )
   ```

2. **For each tool with source code:**
   - Calls `analyze_source()` to find external dependencies
   - Calls `find_internal_calls()` to find calls to other tools
   - Builds `_tool_dependencies` list
   - Computes version hash using `compute_version()`

3. **Detects circular dependencies:**
   ```python
   cycle = detect_circular(tools, tool_map)
   if cycle:
       raise RuntimeError(f"Circular dependency detected: {cycle_str}")
   ```

4. **Sorts tools topologically:** Ensures dependencies are uploaded before dependents.

5. **Fetches existing backend tools:** Compares versions to avoid re-uploading unchanged tools.

6. **Uploads changed tools:** Calls `client.deploy_tool(bundle)` for each tool with a different version.

7. **Deploys agent configuration:**
   ```python
   deployment = {
       "agent": self.agent.to_config(),
       "tools": [...],
   }
   response = await client.deploy_agent(agent_config=deployment)
   ```

8. **Updates agent state:**
   ```python
   self.agent.config.mode = "deployed"
   self.agent.config.agent_id = response["id"]
   self.agent.config.backend_url = backend_url
   ```

**Returns:** Deployment response dict with `id` and `status`.

**Raises:**
- `RuntimeError` — If circular dependencies detected or tool upload fails

### `delete()` — Delete Agent from Backend

```python
async def delete(self) -> None:
```

**Logic:**
1. Verifies agent is deployed (`agent.config.agent_id` is set)
2. Calls `client.delete_agent(agent_id=...)`
3. Resets agent state to local:
   ```python
   self.agent.config.agent_id = None
   self.agent.config.mode = "local"
   ```

**Raises:** `RuntimeError` if agent is not deployed.

### `load_agent()` — Class Method

```python
@classmethod
async def load_agent(
    cls,
    agent_id: str,
    backend_url: str,
    backend_api_key: str | None = None,
    backend_headers: dict[str, str] | None = None,
    client: BackendClient | None = None,
) -> Agent:
```

Loads an existing agent from the backend.

**Tool resolution process:**
1. Fetches agent config from backend (includes tool configs)
2. Creates `Agent` via `Agent.from_config()`
3. Tools are reconstructed from config via `Tool.from_config()`
4. If a tool is not available locally, it's reconstructed from its stored bundle (source + dependencies)
5. Missing tools that cannot be reconstructed are logged as warnings but do not prevent loading

**Why this design?** Allows agents to be portable — they can be created on one machine and loaded on another without having the original tool definitions installed.

**Client parameter:** Callers are encouraged to pass a persistent `BackendClient` to avoid creating ephemeral connections. When `None`, a temporary client is created internally.

---

## Agent Data Flow

### Local Agent Execution

```
User input
    │
    ▼
create_default_agent()
    │
    ├─ Load config (YAML > env > defaults)
    ├─ Create default tools (memory + context)
    └─ Create Agent with policy
         │
         ▼
    agent.run(user_input)
         │
         ▼
    SDK processes message
         │
         ▼
    LLM generates response
    (possibly with tool calls)
         │
         ▼
    Tools execute
    ├─ remember/recall (memory)
    ├─ search_context_grep (context)
    └─ keyboard/mouse/screen (CUA)
         │
         ▼
    Results stored in session
         │
         ▼
    Response returned
```

### Deploy Flow

```
AgentLifecycle(agent)
    │
    ▼
deploy()
    │
    ├─ Analyze each tool's source code
    ├─ Find external dependencies
    ├─ Find internal tool dependencies
    ├─ Compute version hashes
    ├─ Detect circular dependencies
    ├─ Topologically sort tools
    ├─ Fetch existing backend tools
    ├─ Upload only changed tools
    ├─ Deploy agent config
    └─ Update agent mode to "deployed"
```

---

## Design Decisions

1. **Lazy client creation:** The `BackendClient` is only created when needed (first deploy/delete/load call).

2. **Tool dependency analysis:** Before deploying, the lifecycle manager analyzes tool source code to build a dependency graph. This ensures tools are uploaded in the correct order and versioned correctly.

3. **Version computation:** Tool versions are computed from source code + dependency versions, enabling automatic re-deployment when tools change.

4. **Class method for load:** `load_agent()` is a class method because it creates a new `Agent` instance rather than modifying an existing one.

6. **Mode mutation:** The agent's `mode` and `agent_id` are mutated during deploy/delete operations rather than creating new agent instances. This keeps the same agent object alive throughout its lifecycle.
