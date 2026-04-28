# Agent Package Documentation

The `agent/` package is the heart of the TINYCUA SDK. It defines what an agent is, how it's configured, how it executes, and how it can be customized.

**Package path:** `tinycua_sdk/agent/`  
**Files documented:**
- `agent.py` - Main Agent class
- `executor.py` - Execution capabilities
- `definition.py` - Base configuration and properties
- `config.py` - AgentConfig and AgentPolicy dataclasses
- `loader.py` - AGENT.md file loader
- `loop.py` - Execution loops (BaseLoop, ReactLoop)
- `loop_resolver.py` - Loop dependency analysis
- `hooks.py` - Hook system for loop customization
- `templates.py` - Built-in agent templates
- `tool_resolver.py` - Tool resolution from specs
- `skill_resolver.py` - Skill tool resolution and activation
- `validator.py` - Configuration validation

---

## agent.py - The Agent Class

### Purpose

`Agent` is the primary user-facing class. It inherits from `AgentExecutor` and adds backward-compatible lifecycle methods (`deploy()`, `delete()`, `load_agent()`) and template-based creation (`from_template()`).

### Design Rationale

The class uses **lazy imports** for `tinycua.agent.lifecycle.AgentLifecycle` to avoid importing the main `tinycua` package at module load time. This keeps the SDK lightweight and avoids circular dependencies.

### Constructor

```python
Agent(
    name: str = "assistant",
    instructions: str = "",
    system_prompt: str = "You are a helpful assistant.",
    model: str = "gpt-4o-mini",
    provider: str = "openai",
    base_url: str | None = None,
    api_key: str | None = None,
    tools: list[Tool] | None = None,
    policy: AgentPolicy | None = None,
    mode: str = "local",
    backend_url: str | None = None,
    backend_api_key: str | None = None,
    backend_headers: dict[str, str] | None = None,
    agent_id: str | None = None,
    runner: Any = None,
    sub_agents: list[Agent] | None = None,
    max_depth: int = AgentExecutor.DEFAULT_MAX_DEPTH,
    current_depth: int = 0,
    keywords: list[str] | None = None,
    strip_thinking: bool | list[str] | None = None,
    loop: Any = None,
    skills: list[str] | None = None,
    planning_prompt: str | None = None,
    short_term_memory: ShortTermMemory | None = None,
    long_term_memory: LongTermMemory | None = None,
)
```

**Key parameters:**
- `mode`: `"local"` (default) or `"deployed"`
- `backend_url` / `backend_api_key`: For remote execution
- `sub_agents`: Child agents for task delegation
- `max_depth`: Maximum delegation depth (default: 3)
- `keywords`: Used by Runner to route tasks to sub-agents
- `strip_thinking`: Patterns to remove from LLM output (e.g., `<think>...</think>`)
- `loop`: Custom loop instance or config
- `skills`: Names of skills to auto-load

### Memory Properties

```python
@property
def short_term_memory(self) -> ShortTermMemory | None:
    return self._short_term_memory

@property
def long_term_memory(self) -> LongTermMemory | None:
    return self._long_term_memory
```

These expose the memory instances passed to the constructor. They are **not** automatically created - the user must provide them.

### Lifecycle Methods

```python
async def deploy(self) -> dict[str, Any]:
    from tinycua.agent.lifecycle import AgentLifecycle
    lifecycle = AgentLifecycle(self)
    return await lifecycle.deploy()
```

- `deploy()`: Uploads agent config to backend, returns `agent_id`
- `delete()`: Removes agent from backend
- `load_agent(cls, agent_id, backend_url, ...) -> Agent`: Class method to load existing deployed agent

All four methods lazily import from `tinycua.agent.lifecycle` (the main TINYCUA package, not the SDK).

### from_template() Class Method

```python
@classmethod
def from_template(cls, template_name: str, overrides: dict | None = None, **kwargs) -> Agent
```

Creates an agent from pre-built templates ("coder", "researcher", "assistant"):

1. Calls `get_template(template_name)` to get base config dict
2. Applies `overrides` via `apply_template_overrides()`
3. Extracts fields: name, system_prompt, model, provider, tools, skills, loop, policy, keywords
4. Resolves tool string names to `Tool` instances via `ToolRegistry`
5. Resolves loop config via `resolve_loop()`
6. Creates `AgentPolicy` from policy dict
7. Instantiates `Agent` with all extracted parameters

**Why this design?** It separates template storage from template application, allowing users to customize templates without modifying the source.

---

## executor.py - Agent Execution

### Purpose

Adds execution capabilities on top of `AgentDefinition`: `run()`, `run_sync()`, `stream()`, `stream_sync()`, plus cancel control and runner/loop management.

### ToolExecutor Class

```python
class ToolExecutor:
    def execute(self, tool_name: str, tool: Any, arguments: dict | None = None) -> dict
    async def execute_async(self, tool_name: str, tool: Any, arguments: dict | None = None) -> dict
```

Provides **standardized error handling** for tool execution:
- Returns `{"success": True, "result": ..., "tool_name": ...}` on success
- Returns `{"success": False, "error": ..., "tool_name": ..., "ref_id": ...}` on failure
- Logs errors to the `tinycua_sdk.security` logger with UUID reference IDs
- Catches: `TimeoutError`, `ValueError`, `TypeError`, `RuntimeError`, `OSError`, `AttributeError`

**Why return dicts instead of raising?** This allows the agent to continue execution even when a tool fails, passing the error back to the LLM as context.

### Global Config Cache

```python
_global_config: SDKConfig | None = None

def _get_global_config() -> SDKConfig:
    global _global_config
    if _global_config is None:
        _global_config = SDKConfig.load()
    return _global_config
```

Lazy-loaded singleton for `SDKConfig` to avoid repeated environment parsing.

### AgentExecutor Class

Inherits from `AgentDefinition` and adds:

#### Cancel Control

```python
@property
def cancel_event(self) -> asyncio.Event:
    if not hasattr(self, "_cancel_event") or self._cancel_event is None:
        self._cancel_event = asyncio.Event()
    return self._cancel_event

def cancel(self) -> None:
    self.cancel_event.set()
```

Uses `asyncio.Event` for thread-safe cancellation signaling. The event is lazily created to avoid overhead for agents that never need cancellation.

#### Runner Management

```python
def _get_runner(self) -> Runner:
    from tinycua_sdk.runner import Runner
    if self._local_runner is None:
        self._local_runner = Runner(self.config)
    return self._local_runner
```

Lazy-instantiates the `Runner` with the agent's config.

#### Loop Loading

```python
def _load_loop(self) -> DefaultLoop:
    if self._loop_cache is not None:
        return self._loop_cache
    runner = Runner(self.config, cancel_event=self.cancel_event)
    loop_config = getattr(self.config, "loop", None)
    
    # If already a loop instance, inject runner and cache
    if loop_config is not None and hasattr(loop_config, "run"):
        loop_config.runner = runner
        self._loop_cache = loop_config
        return loop_config
    
    # Resolve string/dict to loop instance
    loop = resolve_loop(loop_config)
    loop.runner = runner
    self._loop_cache = loop
    return loop
```

This method:
1. Caches the loop to avoid re-creation
2. Detects if `loop` is already an instance vs. a config dict/string
3. Injects the `Runner` into the loop (loops need a runner for LLM calls)

#### Execution Modes

**Local execution:**
```python
async def run(self, user_input: str, ..., force_local: bool = False) -> Union[str, Any]:
    if self.is_deployed and not force_local:
        return await self._run_deployed(user_input, trace=trace)
    self.reset_cancel()
    loop = self._load_loop()
    return await loop.run(self, user_input, trace=trace, ...)
```

The execution path is chosen based on `mode`:
- `"deployed"`: Calls `_run_deployed()` → `BackendClient.execute()` with SSE streaming
- `"local"`: Loads custom loop, calls `loop.run()`

**Why `force_local`?** Allows testing local behavior even when agent has backend config set.

#### Backend Client Caching

```python
def _get_client(self) -> BackendClient:
    if self._client is None:
        backend_url, backend_api_key, backend_headers = self._get_backend_config()
        self._client = BackendClient(...)
    return self._client
```

Caches the `BackendClient` to avoid creating new HTTP connections per call. Priority for config: agent config > global SDKConfig.

#### Security Integration

```python
@staticmethod
def check_tool_permission(tool_name: str) -> bool:
    from tinycua_sdk.security.permissions import PermissionSystem
    ps = PermissionSystem()
    return ps.check_permission(tool_name)

@staticmethod
def check_tool_approval_required(tool_name: str) -> bool:
    from tinycua_sdk.security.permissions import PermissionSystem
    ps = PermissionSystem()
    return ps.requires_approval(tool_name)
```

Static methods for permission checking, used by both `AgentExecutor` and `Runner`.

---

## definition.py - Agent Definition

### Purpose

Base class holding agent configuration and properties. Provides config management, property accessors, sub-agent management, tool management, and serialization.

### Constants

```python
MAX_SUB_AGENTS = 10
DEFAULT_MAX_DEPTH = 3
```

Hard limits to prevent runaway delegation trees.

### Constructor

```python
def __init__(self, name="assistant", instructions="", system_prompt="...", ...):
    self.config = AgentConfig(name=name, instructions=..., tools=tools or [], ...)
    self._sub_agents = sub_agents or []
    self.max_depth = max_depth
    self.current_depth = current_depth
    self.keywords = keywords or []
```

All configuration is stored in an `AgentConfig` instance. Properties delegate to `self.config`.

### Property Accessors

```python
@property
def name(self) -> str:
    return self.config.name

@property
def mode(self) -> str:
    return self.config.mode

@property
def is_deployed(self) -> bool:
    return self.config.mode == "deployed"
```

These provide clean read-only access to config fields. `is_deployed` is a convenience property.

### Sub-Agent Management

```python
def add_sub_agent(self, agent: Agent) -> None:
    if len(self.config.sub_agents) >= self.MAX_SUB_AGENTS:
        raise ValueError(f"Maximum {self.MAX_SUB_AGENTS} sub-agents allowed")
    self.config.sub_agents.append(agent)
    self._sub_agents = self.config.sub_agents
```

Enforces the sub-agent limit. Keeps `self._sub_agents` in sync with `self.config.sub_agents`.

```python
def _get_all_sub_agents(self, depth: int = 0) -> dict[str, Any]:
    if depth >= self.max_depth:
        return {self.name: self}
    result = {self.name: self}
    for sub in self._sub_agents:
        result.update(sub._get_all_sub_agents(depth + 1))
    return result
```

Recursively collects all sub-agents up to `max_depth`. Returns a flat dict mapping names to agents.

```python
def _find_sub_agent_for_task(self, task: str) -> Any:
    task_lower = task.lower()
    for sub in self._sub_agents:
        sub_keywords = sub.keywords or [sub.name.lower()]
        if any(kw.lower() in task_lower for kw in sub_keywords):
            return sub
    return None
```

Simple keyword-based task routing. Used by `Runner` to find the right sub-agent for delegation.

### Serialization

```python
def to_config(self) -> dict[str, Any]:
    return self.config.to_config()

@classmethod
def from_config(cls, data: dict[str, Any]) -> AgentDefinition:
    config = AgentConfig.from_config(data)
    agent = cls(name=config.name, instructions=config.instructions, ...)
    return agent
```

Delegates to `AgentConfig` for actual serialization logic. Round-trips through dict format.

---

## config.py - Agent Configuration

### Purpose

Defines `AgentPolicy` and `AgentConfig` dataclasses, plus serialization/deserialization from JSON, YAML, and dicts.

### _substitute_env_vars()

```python
def _substitute_env_vars(data: dict[str, Any]) -> dict[str, Any]:
    pattern = re.compile(r"\$\{(\w+)\}")
    # Recursively replaces ${VAR_NAME} with os.environ[VAR_NAME]
```

Supports environment variable substitution in config files. Raises `ValueError` if variable is not set.

### AgentPolicy

```python
@dataclass
class AgentPolicy:
    max_tool_calls: int = 10
    parallel_tool_calls: bool = True
    temperature: float = 1.0
```

Simple behavior policy. `max_tool_calls` prevents infinite tool loops.

### AgentConfig

```python
@dataclass
class AgentConfig:
    name: str = "assistant"
    instructions: str = ""
    system_prompt: str = "You are a helpful assistant."
    model: str = "gpt-5-nano"  # Note: default changed from gpt-4o-mini
    provider: str = "openai"
    base_url: str | None = None
    api_key: str | None = None
    tools: list[str | Tool] = field(default_factory=list)
    policy: AgentPolicy = field(default_factory=AgentPolicy)
    mode: str = "local"
    backend_url: str | None = None
    backend_api_key: str | None = None
    backend_headers: dict[str, str] | None = None
    agent_id: str | None = None
    strip_thinking: bool | list[str] | None = None
    sub_agents: list["Agent"] = field(default_factory=list)
    loop: Any = None
    skills: list[str] = field(default_factory=list)
    skill_dirs: list[Path] = field(default_factory=list)
    auto_load_dependencies: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    planning_prompt: str | None = None
```

**Key design notes:**
- `tools` can contain `Tool` instances or strings (for lazy resolution)
- `loop` can be `None`, `str`, `dict`, or `BaseLoop` instance
- `skills` and `skill_dirs` enable Stage 3 skill loading
- `metadata` provides backward compatibility and extensibility

### Serialization Methods

**to_config()** serializes the config to a dict. Special handling for:
- `Tool` instances → `tool.to_config()`
- `AgentPolicy` → dict with `max_tool_calls`, `parallel_tool_calls`, `temperature`
- `loop` → Extracts class source code, dependencies, and helpers via `analyze_loop_source()`
- `skill_dirs` → converted to strings

**Why serialize loop source code?** This allows deploying custom loops to the backend - the backend can reconstruct the loop class from source.

**from_config()** reverses the process:
- `tools` data can be `Tool` instances, dicts (reconstruct via `Tool.from_config()`), or strings (lazy)
- `skills` checked in both top-level and `metadata` for Stage 1 compatibility
- `loop` stored as raw config for later materialization

### File I/O

```python
@classmethod
def from_json(cls, json_data: str | Path | dict[str, Any]) -> "AgentConfig"
@classmethod
def from_json_file(cls, path: Path | str) -> "AgentConfig"
@classmethod
def from_yaml_file(cls, path: Path | str) -> "AgentConfig"
def to_json(self, indent: int = 2, redact_sensitive: bool = False) -> str
def to_yaml(self, redact_sensitive: bool = False) -> str
def to_json_file(self, path: Path | str, indent: int = 2) -> None
def to_yaml_file(self, path: Path | str) -> None
```

Flexible input handling:
- `from_json()` accepts string (JSON or file path), `Path`, or `dict`
- Auto-detects file paths by checking for `.json` extension and path separators
- Applies `_substitute_env_vars()` after parsing
- `redact_sensitive` masks `api_key` values with `***REDACTED***`

---

## loader.py - AGENT.md Loader

### Purpose

Loads agent configurations from `AGENT.md` files (YAML frontmatter + Markdown instructions).

### Exceptions

```python
class AgentNotFoundError(Exception):
    """Raised when AGENT.md file does not exist."""

class AgentParseError(Exception):
    """Raised when AGENT.md cannot be parsed."""
```

### AgentLoader

```python
class AgentLoader:
    def load_from_markdown(self, path: Path) -> AgentConfig
```

**Loading process:**
1. Determine if path is file or directory
2. Read `AGENT.md` content
3. Split by `---` to extract YAML frontmatter and Markdown body
4. Parse YAML into `metadata` dict
5. Extract fields: name, model, provider, tools, policy, loop, skills
6. Resolve tools via `ToolResolver`
7. Load skill tools via `_load_skill_tools()`
8. Build `AgentConfig` with merged data

### Skill Tool Loading

```python
def _load_skill_tools(
    self, skill_names: list[str], skill_dirs: list[Path], auto_load_dependencies: bool = True
) -> tuple[list[Tool], list[str]]
```

**Process:**
1. Initialize `SkillRegistry`, `SkillToolResolver`, `SkillActivator`
2. Scan `skill_dirs` for `SKILL.md` files
3. For each requested skill:
   - Check if already loaded (avoid duplicates)
   - Check conditional activation via `SkillActivator.should_activate_skill()`
   - Resolve tools via `SkillToolResolver.resolve_skill_tools()`
   - Append skill instructions
   - Recursively load dependencies if `auto_load_dependencies=True`
4. Returns `(resolved_tools, skill_instructions)`

**Security:** `_validate_skill_dir()` ensures skill directories are within allowed bases (`Path.cwd()`, `Path.home()`) to prevent directory traversal.

---

## loop.py - Execution Loops

### Purpose

Defines customizable execution strategies for agents.

### BaseLoop

```python
class BaseLoop:
    def __init__(self, runner: Runner = None):
        self.runner = runner
        self._hooks = HookManager()
```

The default loop simply delegates to `Runner.run()` or `Runner.run_sse()`:

```python
async def run(self, agent, user_input, trace=False, verbose=False, stream_sse=False, **kwargs):
    context = {"agent": agent, "user_input": user_input, ...}
    context = await self._hooks.execute_pre_hooks(context)
    
    # Configure runner from context
    self.runner.trace = context.get("trace", trace)
    self.runner.verbose = context.get("verbose", verbose)
    self.runner.stream_sse = context.get("stream_sse", stream_sse)
    
    if context.get("stream_sse"):
        result = self.runner.run_sse(...)
    else:
        result = await self.runner.run(...)
    
    context["result"] = result
    context = await self._hooks.execute_post_hooks(context)
    return context.get("result", result)
```

**Why pre/post hooks?** They allow middleware to modify context before execution and results after execution, without subclassing.

### ReactLoop

```python
class ReactLoop(BaseLoop):
    def __init__(self, runner: Runner = None, max_iterations: int = 5):
        super().__init__(runner=runner)
        self.max_iterations = max_iterations
```

Implements the **ReAct pattern** (Reason + Act):

```python
async def run(self, agent, user_input, ...):
    messages = self.runner.build_messages(user_input)
    tools = self.runner.get_tool_configs()
    
    for iteration in range(self.max_iterations):
        response = await self.runner.call_llm(messages, tools)
        tool_calls = self._extract_tool_calls(response)
        
        if not tool_calls:
            content = self._extract_content(response)
            return content
        
        tool_messages, results = await self.runner.execute_tool_loop(tool_calls)
        messages.extend(tool_messages)
    
    return "Max iterations reached"
```

**Iteration:**
1. Call LLM with current messages + tool definitions
2. Extract tool calls from response
3. If no tool calls, return content
4. Execute tools, add results to messages
5. Repeat

**Why explicit iterations?** Makes the reasoning process transparent and limits the number of tool calls.

### resolve_loop()

```python
def resolve_loop(loop_config: Any) -> BaseLoop:
    if loop_config is None:
        return BaseLoop()
    if isinstance(loop_config, BaseLoop):
        return loop_config
    if isinstance(loop_config, str):
        loop_type = loop_config.lower()
        _validate_loop_type(loop_type)
        if loop_type == "default":
            return BaseLoop()
        elif loop_type == "react":
            return ReactLoop()
    if isinstance(loop_config, dict):
        loop_type = loop_config.get("type", "default").lower()
        kwargs = {k: v for k, v in loop_config.items() if k != "type"}
        # Filter kwargs to valid constructor params
        ...
```

Flexible loop resolution supporting:
- `None` → `BaseLoop()`
- `BaseLoop` instance → pass through
- `str` → "default" or "react"
- `dict` → `{type: "react", max_iterations: 10}`

---

## loop_resolver.py - Loop Dependency Analysis

### Purpose

Analyzes custom loop source code to extract dependencies and helper functions for deployment.

```python
def analyze_loop_source(source: str) -> tuple[list[str], list[dict[str, str]]]:
    dependencies = analyze_tool_source(source)  # From tools/resolver.py
    helpers = extract_helper_functions(source)
    return dependencies, helpers
```

**analyze_loop_source()** returns:
- `dependencies`: List of pip package names needed by the loop
- `helpers`: List of helper function dicts with `name` and `source`

**extract_helper_functions()** uses `ast.parse()` to find non-async function definitions (excluding `run`), then extracts their source via `ast.get_source_segment()`.

**Why extract helpers?** When deploying a custom loop to the backend, the backend needs both the loop class AND any helper functions it depends on.

---

## hooks.py - Hook System

### Purpose

Provides pre-execution and post-execution hooks for agent loops.

### Hook Types

```python
HookFunc = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
```

A hook is an async function that receives a context dict and returns a modified context dict.

### HookConfig

```python
@dataclass
class HookConfig:
    func: HookFunc
    order: int = 0
    name: str | None = None
    enabled: bool = True
```

Hooks execute in order (lowest `order` first). Can be disabled individually.

### HookManager

```python
class HookManager:
    def add_pre_hook(self, func: HookFunc, order: int = 0, name: str | None = None) -> None
    def add_post_hook(self, func: HookFunc, order: int = 0, name: str | None = None) -> None
    async def execute_pre_hooks(self, context: dict[str, Any]) -> dict[str, Any]
    async def execute_post_hooks(self, context: dict[str, Any]) -> dict[str, Any]
```

**Execution:** Iterates through hooks in order, passing the context through each one. If a hook is disabled, it's skipped.

**Example usage:**
```python
async def log_hook(context):
    context["start_time"] = time.time()
    return context

loop.add_pre_hook(log_hook, order=0, name="logger")
```

---

## templates.py - Agent Templates

### Purpose

Pre-built agent configurations for quick agent creation.

### AgentTemplate TypedDict

```python
class AgentTemplate(TypedDict, total=False):
    name: str
    description: str
    system_prompt: str
    model: str
    provider: str
    tools: list[str]
    skills: list[str]
    loop: str | dict
    policy: dict
    keywords: list[str]
    instructions: str
    base_url: str | None
    api_key: str | None
    strip_thinking: bool | list[str] | None
    max_depth: int
    sub_agents: list
    mode: str | None
    backend_url: str | None
    backend_api_key: str | None
    backend_headers: dict | None
    agent_id: str | None
```

`total=False` means all fields are optional.

### Built-in Templates

| Template | Purpose | Default Tools | Loop | Keywords |
|----------|---------|---------------|------|----------|
| `coder` | Code generation/debugging | bash, read_file, write_file, list_directory | default | code, program, debug, implement, fix |
| `researcher` | Research and analysis | search_web, read_file, visit_url | react | research, find, analyze, investigate, explain |
| `assistant` | General-purpose help | (none) | default | help, question, assist, general |

### Template Functions

```python
def get_template(name: str) -> AgentTemplate
def list_templates() -> list[str]
def template_exists(name: str) -> bool
def validate_template(template: dict) -> None
def apply_template_overrides(template: AgentTemplate, overrides: dict | None) -> AgentTemplate
```

**apply_template_overrides()** validates override keys against `ALLOWED_OVERRIDE_FIELDS`, then:
- Deep-merges `policy` dicts
- Replaces `tools` and `skills` lists
- Directly overrides scalar fields

**Why validate overrides?** Prevents typos and ensures only valid fields are modified.

---

## tool_resolver.py - Tool Resolution

### Purpose

Parses and resolves tool specifications to `Tool` instances with security safeguards.

### ToolResolver

```python
class ToolResolver:
    INLINE_TOOL_TIMEOUT: float = 5.0
    SANDBOX_MODE: bool = False
```

**Security features:**
1. AST validation of inline tool source
2. Dangerous pattern detection (`__import__`, `open`, `exec`, `eval`, `compile`)
3. Subprocess execution with timeout for inline tools
4. Temp file cleanup after execution

### Resolution Process

```python
def resolve(self, tool_specs: list[Any]) -> list[str | Tool]:
    for spec in parsed_specs:
        if isinstance(spec, str):
            resolved = self.resolve_tool_reference(spec)
        elif isinstance(spec, dict):
            if "tool" in spec:
                tool = self.resolve_inline_tool(spec["tool"])
            elif "mcp" in spec:
                mcp_config = self.resolve_mcp_tool(spec)
```

Supports three tool specification types:
- **String**: Name reference → lookup in `ToolRegistry`
- **Dict with "tool" key**: Inline Python source with `@tool` decorator
- **Dict with "mcp" key**: MCP (Model Context Protocol) server configuration

### Inline Tool Execution

```python
def resolve_inline_tool(self, source: str) -> Tool:
    self._validate_tool_source(source)
    tool = self._execute_inline_tool_with_timeout(source, self.INLINE_TOOL_TIMEOUT)
    self.registry.register(name=tool.name, tool=tool, schema=tool.to_config())
    return tool
```

**Steps:**
1. Parse source with `ast.parse()` → validate syntax
2. Check for dangerous function calls
3. Extract function info (name, docstring, parameters, defaults)
4. Generate a script that creates the `Tool` and prints its config
5. Execute script in subprocess with `subprocess.run(timeout=5)`
6. Parse `__TOOL_CONFIG__:` output line
7. Reconstruct `Tool.from_config(tool_config)`
8. Register in `ToolRegistry`

**Why subprocess?** Provides true process isolation and timeout capability. The parent process cannot reliably timeout arbitrary Python code execution within the same process.

### MCP Tool Resolution

```python
def resolve_mcp_tool(self, mcp_config: dict[str, Any]) -> dict[str, Any]:
    # Validates required fields: "mcp", "server"
    # Validates types: both must be non-empty strings
    # Validates optional "config" field: must be dict or None
    return mcp_config
```

MCP configs are returned as-is after validation. They're stored in agent metadata for later use by an MCP client.

---

## skill_resolver.py - Skill Tool Resolution

### Purpose

Resolves skill tool names to `Tool` instances and handles conditional skill activation.

### SkillToolResolver

```python
class SkillToolResolver:
    def resolve_skill_tools(self, skill: Skill) -> list[Tool]
    def get_resolved_tools(self, skill_names: list[str], registry: SkillRegistry) -> list[Tool]
```

**Key design principle:** Read-only lookups from `ToolRegistry`. Does NOT register tools.

### SkillActivator

```python
class SkillActivator:
    PLATFORM_MAP = {"macos": "darwin", "linux": "linux", "windows": "win32"}
    
    def should_activate_skill(
        self, skill: Skill, available_toolsets: set[str], available_tools: set[str]
    ) -> bool
```

**Conditional activation logic:**
- `platforms`: AND with other conditions; current platform must match
- `requires_toolsets`: OR semantics - any toolset match is sufficient
- `fallback_for_toolsets`: OR semantics - if any match, skill is HIDDEN
- `requires_tools`: OR semantics - any tool match is sufficient
- `fallback_for_tools`: OR semantics - if any match, skill is HIDDEN

**Between different condition types:** AND semantics (all must pass).

**Example:** A skill with `requires_toolsets: ["git"]` and `platforms: ["linux"]` will only activate on Linux systems where git tools are available.

---

## validator.py - Configuration Validation

### Purpose

Validates agent configurations and reports errors/warnings.

### SeverityLevel

```python
class SeverityLevel(Enum):
    ERROR = "error"
    WARNING = "warning"
```

### ValidationError

```python
@dataclass
class ValidationError:
    field: str
    message: str
    severity: SeverityLevel
```

### AgentConfigValidator

```python
class AgentConfigValidator:
    KNOWN_PROVIDERS = {"openai", "openai-compatible", "google", "local"}
    KNOWN_MODELS = {"gpt-5-nano", "gpt-4o-mini", "gpt-4o", ...}
    KNOWN_LOOP_TYPES = {"default", "reflective", "reasoning", "simple", "react", "plan", "react-reasoning"}
    TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
```

**Validation checks:**
1. **Name**: Required, non-empty
2. **Provider**: Warning if unknown
3. **Temperature**: Warning if > 2.0
4. **Loop type**: Warning if unknown
5. **Tool names**: Warning if contains invalid characters

**Why warnings instead of errors for unknown providers/models?** The SDK supports custom/local providers that may not be in the known list. Errors would be too restrictive.

---

## Inter-Module Data Flow

### Agent Creation Flow
```
User Code
  → Agent.__init__() → AgentExecutor.__init__() → AgentDefinition.__init__()
    → AgentConfig.__init__()
  → (optional) Agent.from_template()
    → get_template() → apply_template_overrides()
    → ToolRegistry.get() → resolve_loop()
```

### Execution Flow
```
Agent.run()
  → if deployed: _run_deployed() → BackendClient.execute()
  → if local: _load_loop() → loop.run()
    → HookManager.execute_pre_hooks()
    → Runner.run() or Runner.run_sse()
    → HookManager.execute_post_hooks()
```

### AGENT.md Loading Flow
```
AgentLoader.load_from_markdown(path)
  → _parse_agent_md()
    → yaml.safe_load(frontmatter)
    → ToolResolver.resolve(tools)
    → _load_skill_tools()
      → SkillRegistry.load_skills_from_directory()
      → SkillActivator.should_activate_skill()
      → SkillToolResolver.resolve_skill_tools()
    → AgentConfig.from_config()
```
