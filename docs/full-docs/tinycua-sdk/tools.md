# Tools Package Documentation

The `tools/` package defines the tool system: how functions become tools, how their schemas are generated, how they're resolved, and how they integrate with external protocols.

**Package path:** `tinycua_sdk/tools/`

---

## decorators.py - Tool Model and Decorator

### Purpose

Provides the `@tool` decorator and `Tool` dataclass - the foundation of the entire tool system.

### Tool Dataclass

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
    _is_builtin: bool = False
```

**Field purposes:**
- `name` / `description` / `parameters`: Public API schema
- `_fn`: The actual callable to invoke
- `_source`: Original Python source code (for deployment)
- `_external_dependencies`: pip packages required (e.g., `["requests"]`)
- `_tool_dependencies`: Other tools this tool depends on
- `_version`: Version string for deployment
- `_is_builtin`: Flag for built-in vs. custom tools

### to_config() and to_bundle()

```python
def to_config(self) -> dict[str, Any]:
    return {
        "name": self.name,
        "description": self.description,
        "parameters": self.parameters,
    }

def to_bundle(self) -> dict[str, Any]:
    return {
        "name": self.name,
        "description": self.description,
        "parameters": self.parameters,
        "source": self._source,
        "external_dependencies": self._external_dependencies,
        "tool_dependencies": self._tool_dependencies,
        "version": self._version,
    }
```

- `to_config()`: Minimal schema for LLM API calls
- `to_bundle()`: Full deployment package including source and dependencies

### invoke()

```python
def invoke(self, **kwargs: Any) -> Any:
    if self._fn is None:
        raise RuntimeError(f"Tool {self.name} has no function to invoke")
    result = self._fn(**kwargs)
    if asyncio.iscoroutine(result):
        try:
            asyncio.get_running_loop()
            return result
        except RuntimeError:
            return asyncio.run(result)
    return result
```

**Async handling:**
1. Invokes the function with provided kwargs
2. If result is a coroutine:
   - If inside an async context (running loop exists), returns the coroutine (caller must await)
   - If outside async context, runs it with `asyncio.run()`

**Why this design?** Supports both sync and async tool functions transparently. The caller can always `await` the result safely.

### from_config()

```python
@classmethod
def from_config(cls, data: dict[str, Any]) -> Tool:
    return cls(
        name=data["name"],
        description=data["description"],
        parameters=data.get("parameters", {}),
        _tool_dependencies=data.get("tool_dependencies", []),
        _version=data.get("version"),
    )
```

Reconstructs a Tool from config dict. Note: `_fn` is NOT restored - the reconstructed tool can be used for schema but not invocation until a handler is attached.

### _make_tool() - Factory Function

```python
def _make_tool(fn: Callable, dependencies: list[str]) -> Tool:
    sig = inspect.signature(fn)
    description = fn.__doc__ or ""
    
    params = {}
    required = []
    for param_name, param in sig.parameters.items():
        schema = type_to_json_schema(param.annotation)
        params[param_name] = schema
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            params[param_name]["default"] = param.default
    
    source = inspect.getsource(fn)
    
    return Tool(
        name=fn.__name__,
        description=description.strip().split("\n")[0],
        parameters={"type": "object", "properties": params, "required": required},
        _fn=fn,
        _source=source,
        _external_dependencies=dependencies,
    )
```

**Schema generation process:**
1. Extract function signature via `inspect.signature()`
2. For each parameter:
   - Convert type annotation to JSON Schema via `type_to_json_schema()`
   - If no default value, add to `required` list
   - If default value exists, add to schema as `default`
3. Extract source code via `inspect.getsource()`
4. Build `Tool` with generated schema

**Why split description by newline?** Uses only the first line of the docstring as the description, keeping the schema concise for LLM context windows.

### @tool Decorator

```python
def tool(dependencies: list[str] | Callable | None = None):
    if callable(dependencies):
        return _make_tool(dependencies, [])
    
    _external_deps = dependencies or []
    
    def decorator(fn: Callable) -> Tool:
        return _make_tool(fn, _external_deps)
    
    return decorator
```

**Usage patterns:**
```python
@tool
def my_tool(x: int) -> str: ...

@tool()
def my_tool(x: int) -> str: ...

@tool(dependencies=["requests"])
def my_tool(x: int) -> str: ...
```

**Decorator detection:** If `dependencies` is callable, it's the function itself (bare `@tool` usage). Otherwise, it returns a decorator factory.

---

## schema.py - Type-to-JSON-Schema Conversion

### Purpose

Converts Python type annotations into JSON Schema dictionaries for LLM tool definitions.

### Main Function

```python
def type_to_json_schema(type_hint: Any) -> dict[str, Any]:
    # Handle Annotated
    type_hint, description = _handle_annotated(type_hint)
    
    # Check for Enum
    schema = _handle_enum(type_hint, description)
    if schema: return schema
    
    # Check for Union (including Optional)
    schema = _handle_union(type_hint, description)
    if schema: return schema
    
    # Check for List
    schema = _handle_list(type_hint, description)
    if schema: return schema
    
    # Check for Dict
    schema = _handle_dict(type_hint, description)
    if schema: return schema
    
    # Check for primitives
    schema = _handle_primitive(type_hint, description)
    if schema: return schema
    
    # Fallback
    return {"type": "string", "description": description} if description else {"type": "string"}
```

### Supported Type Features

| Python Type | JSON Schema | Notes |
|-------------|-------------|-------|
| `str` | `{"type": "string"}` | |
| `int` | `{"type": "integer"}` | |
| `float` | `{"type": "number"}` | |
| `bool` | `{"type": "boolean"}` | |
| `list[T]` | `{"type": "array", "items": ...}` | Recursive item schema |
| `dict[K, V]` | `{"type": "object"}` | |
| `Optional[T]` | Inner type schema | `NoneType` filtered out |
| `Union[T1, T2]` | `{"anyOf": [...]}` | |
| `Annotated[T, "desc"]` | Type schema + description | |
| `Enum` subclass | `{"type": "string", "enum": [...]}` | Uses `.value` |

### _handle_annotated()

```python
def _handle_annotated(type_hint: Any) -> tuple[Any, str | None]:
    origin = get_origin(type_hint)
    if origin is not None and _is_annotated_origin(origin):
        args = get_args(type_hint)
        base_type = args[0]
        for meta in args[1:]:
            if isinstance(meta, str):
                description = meta
                break
        type_hint = base_type
    return type_hint, description
```

Extracts description metadata from `typing.Annotated[T, "description"]`.

### _handle_union()

```python
def _handle_union(type_hint: Any, description: str | None) -> dict[str, Any] | None:
    origin = get_origin(type_hint)
    if origin in _union_type():
        union_args = get_args(type_hint)
        non_none_args = [a for a in union_args if a is not type(None)]
        
        if len(non_none_args) == 1:
            # Optional[T] - return inner type
            schema = type_to_json_schema(non_none_args[0])
            if description: schema["description"] = description
            return schema
        
        if len(non_none_args) > 1:
            # Union[T1, T2, ...] - generate anyOf
            schema = {"anyOf": [type_to_json_schema(a) for a in non_none_args]}
            if description: schema["description"] = description
            return schema
    return None
```

Special handling for `Optional[T]` (returns inner schema directly) vs. `Union[T1, T2]` (generates `anyOf`).

---

## resolver.py - Tool Dependency Resolution

### Purpose

Analyzes tool source code to extract external dependencies, detect circular dependencies, and compute version hashes.

### STDLIB_MODULES

```python
STDLIB_MODULES: set[str] = {
    "os", "sys", "json", "datetime", "time", "re", "collections",
    "itertools", "functools", "operator", "random", "math", "typing",
    "uuid", "logging", "traceback", "warnings", "contextlib", "pathlib",
    "abc", "copy", "io", "pickle", "sqlite3", "csv", "xml", "html",
    "urllib", "base64", "binascii", "struct", "codecs", "locale",
    "gettext", "threading", "multiprocessing", "concurrent", "asyncio",
    "subprocess", "socket", "ssl", "signal", "platform", "errno",
    "ctypes", "gc", "weakref", "types", "inspect", "dis", "compile",
    "ast", "fractions", "decimal",
}
```

Comprehensive list of Python standard library top-level modules. Imports from these are NOT considered external dependencies.

### analyze_source()

```python
def analyze_source(source: str) -> list[str]:
    tree = ast.parse(source)
    imports: set[str] = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if _is_external_module(module):
                    imports.add(module)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                if _is_external_module(module):
                    imports.add(module)
    
    return sorted(imports)
```

Uses AST parsing to find import statements. Filters out stdlib and `tinycua*` internal packages. Returns sorted list of external pip package names.

**Why AST instead of regex?** More reliable - handles multi-line imports, comments, and string literals containing "import".

### detect_circular()

```python
def detect_circular(tools: list[Any], tool_map: dict[str, Any]) -> list[str] | None:
    graph = {tool.name: {td.get("name", "") for td in tool._tool_dependencies} for tool in tools}
    
    visited: set[str] = set()
    path: list[str] = []
    
    def dfs(node: str) -> list[str] | None:
        if node in visited:
            idx = path.index(node)
            return path[idx:] + [node]
        visited.add(node)
        path.append(node)
        for dep in graph.get(node, set()):
            if dep in tool_map:
                result = dfs(dep)
                if result: return result
        path.pop()
        return None
    
    for tool in tools:
        visited.clear()
        path.clear()
        cycle = dfs(tool.name)
        if cycle: return cycle
    return None
```

Uses DFS to detect circular tool dependencies. Returns the cycle path (e.g., `["A", "B", "A"]`) if found.

**Why check each tool as a starting point?** A graph may have multiple disconnected components. Starting DFS from each node ensures all components are checked.

### compute_version()

```python
def compute_version(source: str, tool_deps: list[dict[str, Any]]) -> str:
    dep_versions = sorted([td.get("version", "") for td in tool_deps])
    content = source + "|" + "|".join(dep_versions)
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

Computes a 16-character SHA256 hash from source code + dependency versions. Used for cache invalidation and deployment versioning.

### topological_sort()

```python
def topological_sort(tools: list[Any]) -> list[Any]:
    # Kahn's algorithm
    graph = {tool.name: {td.get("name", "") for td in tool._tool_dependencies} for tool in tools}
    in_degree = {tool.name: len(graph[tool.name]) for tool in tools}
    
    queue = [name for name, degree in in_degree.items() if degree == 0]
    result = []
    
    while queue:
        node = queue.pop(0)
        result.append(node)
        for tool in tools:
            if node in graph.get(tool.name, set()):
                in_degree[tool.name] -= 1
                if in_degree[tool.name] == 0:
                    queue.append(tool.name)
    
    tool_dict = {t.name: t for t in tools}
    return [tool_dict[name] for name in result if name in tool_dict]
```

Uses **Kahn's algorithm** to sort tools so dependencies come first. This ensures tools are deployed/loaded in the correct order.

---

## parser.py - Safe Command and Math Parsing

### Purpose

Provides safe parsing utilities to prevent injection attacks.

### CommandParser

```python
@dataclass
class ParsedCommand:
    command: str
    args: List[str]
    flags: Dict[str, str]

class CommandParser:
    def parse(self, command_string: str) -> ParsedCommand
```

**Parsing with shlex:**
```python
def parse(self, command_string: str) -> ParsedCommand:
    parts = shlex.split(command_string)
    command = parts[0]
    args = []
    flags = {}
    
    for part in parts[1:]:
        if part.startswith("--"):
            if "=" in part:
                key, value = part[2:].split("=", 1)
                flags[key] = value
            else:
                flags[part[2:]] = ""
        elif part.startswith("-"):
            flags[part[1:]] = ""
        else:
            args.append(part)
    
    return ParsedCommand(command=command, args=args, flags=flags)
```

Uses `shlex.split()` instead of naive string splitting. This properly handles quoted arguments and prevents shell injection.

**Example:**
```python
parser = CommandParser()
cmd = parser.parse('git commit -m "my message" --amend')
# ParsedCommand(command="git", args=["commit"], flags={"m": "my message", "amend": ""})
```

### safe_eval()

```python
def safe_eval(expression: str) -> float:
    allowed_expression_nodes = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Num)
    tree = ast.parse(expression.strip(), mode="eval")
    
    if not isinstance(tree.body, allowed_expression_nodes):
        raise MathEvalError(f"Unsupported expression type: {type(tree.body).__name__}")
    
    visitor = MathEvalVisitor()
    return visitor.visit(tree.body)
```

**Security model:**
1. Parse expression with `ast.parse(mode="eval")`
2. Whitelist only arithmetic AST node types
3. Reject anything else (function calls, attribute access, etc.)
4. Evaluate with a custom `NodeVisitor` that only allows basic math operators

**Allowed operators:** `+`, `-`, `*`, `/`, `//`, `%`, `**`, unary `+`, unary `-`

**Why not just use `eval()`?** `eval()` can execute arbitrary code. This AST-based approach is a secure replacement.

---

## mcp.py - MCP Client Integration

### Purpose

Implements a client for the **Model Context Protocol (MCP)**, a protocol for connecting AI agents to external tool servers.

### MCPClient

```python
class MCPClient:
    def __init__(self, server_url: str, headers: dict | None = None, timeout: int = 30)
```

**Connection lifecycle:**
```python
async def connect(self) -> None:
    self._client = httpx.AsyncClient(base_url=self.server_url, ...)
    await self._fetch_tools()
    self.connected = True
```

### Tool Discovery

```python
async def _fetch_tools(self) -> list[dict[str, Any]]:
    result = await self._request("GET", "/tools")
    self._tools = result.get("tools", [])
    return self._tools

def get_tools(self) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.get("name", ""),
            "description": tool.get("description", ""),
            "input_schema": tool.get("inputSchema", {}),
        }
        for tool in self._tools
    ]
```

Fetches available tools from the MCP server and normalizes them to SDK format.

### Tool Invocation

```python
async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
    tool = self.get_tool(name)
    if tool is None:
        raise ValueError(f"Tool '{name}' not found")
    
    result = await self._request("POST", f"/tools/{name}", json=arguments)
    return result.get("result")
```

Calls an MCP tool by name with JSON arguments. Returns the result from the server's response.

### Error Handling

All methods catch `(httpx.HTTPError, OSError, ValueError, RuntimeError)` and log warnings rather than crashing. This allows graceful degradation if the MCP server is unavailable.

---

## memory.py - Memory Storage Backend

### Purpose

Provides memory storage backends with DB-first + local fallback strategy.

### MemoryBackend (ABC)

```python
class MemoryBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> tuple[str | None, bool]: ...
    @abstractmethod
    def set(self, key: str, value: str) -> dict[str, Any]: ...
    @abstractmethod
    def delete(self, key: str) -> dict[str, Any]: ...
    @abstractmethod
    def list_keys(self) -> list[str]: ...
    @abstractmethod
    def clear(self) -> dict[str, Any]: ...
```

Abstract base defining the memory interface. All methods return dicts with success status for consistent error handling.

### LocalMemoryBackend

```python
class LocalMemoryBackend(MemoryBackend):
    def __init__(self, storage_path: str | None = None)
```

Stores key-value pairs in a JSON file at `~/.tinycua/memory.json`.

**Operations:**
- `_read_memory()`: `json.load()` from file
- `_write_memory()`: `json.dump()` to file
- `get()`: Returns `(value, key in memory)` tuple
- `set()`: Updates file atomically (read → modify → write)

**Why JSON file?** Simple, human-readable, no external dependencies. Suitable for local development.

### RemoteMemoryBackend

```python
class RemoteMemoryBackend(MemoryBackend):
    def __init__(self, backend_url: str, api_key: str | None = None)
```

Communicates with backend API at `/api/v1/memory`.

**Endpoints:**
- `GET /api/v1/memory/{key}` → Get value
- `POST /api/v1/memory` → Set value
- `DELETE /api/v1/memory/{key}` → Delete value
- `GET /api/v1/memory` → List keys
- `DELETE /api/v1/memory` → Clear all

**Fallback behavior:** On any HTTP error, logs warning, sets `self._available = False`, and raises. The caller (HybridMemoryBackend) catches the exception and falls back to local.

### HybridMemoryBackend

```python
class HybridMemoryBackend(MemoryBackend):
    def __init__(self, backend_url: str | None = None, api_key: str | None = None, local_storage_path: str | None = None)
```

Tries remote first, falls back to local on failure.

```python
def _get_backend(self) -> MemoryBackend:
    if self._remote is not None:
        try:
            self._remote.get("_health_check")  # Probe
            return self._remote
        except (httpx.HTTPError, OSError, ValueError):
            pass
    return self._local
```

**Health check probing:** Before each operation, attempts a lightweight `get("_health_check")` to verify remote availability. If it fails, all subsequent operations use local storage until the next successful probe.

---

## memory_tools.py - Memory Tools (Deprecated)

### Purpose

Provides `@tool` decorated functions for agent memory operations. **Deprecated** in favor of `tinycua.agent.tools.memory_tools`.

### Tools

```python
@tool()
def remember(key: str, value: str) -> dict: ...

@tool()
def recall(key: str) -> dict: ...

@tool()
def forget(key: str) -> dict: ...

@tool()
def list_memory() -> dict: ...

@tool()
def clear_memory() -> dict: ...
```

**Backend resolution:**
```python
def _get_memory_backend() -> MemoryBackend:
    global _memory_backend
    if _memory_backend is None:
        backend_url = os.environ.get("TINYCUA_BACKEND_URL")
        api_key = os.environ.get("TINYCUA_API_KEY")
        local_only = os.environ.get("TINYCUA_MEMORY_LOCAL_ONLY", "false").lower() == "true"
        _memory_backend = get_memory_backend(backend_url, api_key, local_only)
    return _memory_backend
```

Lazy-initialized singleton. Reads config from environment variables.

---

## context_tools.py - Context Retrieval Tools (Deprecated)

### Purpose

Provides tools for searching session context. **Deprecated** in favor of `tinycua.agent.tools.context_tools`.

### ContextTools Class

```python
class ContextTools:
    def __init__(self, session_store=None, session_id=None)
```

**Available operations:**
- `search_context_grep(query)`: Text matching search via `SessionStore.search_grep()`
- `search_context_semantic(query)`: Semantic similarity search (not yet implemented)
- `get_context_summary()`: Returns session summary if available
- `get_recent_turns(count)`: Returns recent non-archived messages

**Session ID requirement:** All methods check for an active session ID and return `{"error": "No active session..."}` if not set.

### Tool Factory Functions

```python
def search_context_grep_tool(session_store=None, session_id=None):
    ctx = ContextTools(session_store, session_id)
    @tool()
    def search_context_grep(query: str) -> dict[str, Any]:
        return ctx.search_context_grep(query)
    return search_context_grep
```

Each function creates a `ContextTools` instance and returns a `@tool` decorated function. This closure pattern binds the session context at tool creation time.

---

## Inter-Module Data Flow

### Tool Creation Flow
```
User defines function
  → @tool decorator
    → _make_tool()
      → inspect.signature() → parameter schemas
      → type_to_json_schema() → JSON Schema
      → inspect.getsource() → source code
      → Tool dataclass
        → ToolRegistry.register()
```

### Tool Invocation Flow
```
LLM response contains tool call
  → Runner._chat_direct()
    → json.loads(arguments)
    → Runner.execute_tool()
      → AgentExecutor.check_tool_permission()
      → tool.invoke(**kwargs)
        → self._fn(**kwargs)
      → Result dict
    → Append to messages
  → Next LLM call
```

### MCP Tool Flow
```
Agent config includes MCP tool spec
  → ToolResolver.resolve_mcp_tool()
    → Validation
    → Store in metadata
  → Agent execution
    → (Future) MCPClient.connect(server_url)
    → MCPClient.call_tool(name, arguments)
      → HTTP POST /tools/{name}
      → Return result
```
