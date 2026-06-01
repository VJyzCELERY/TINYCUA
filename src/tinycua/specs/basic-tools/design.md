# Design Document: Prototype M1 — Basic Tools

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-02

---

## Overview

Implement the basic tool layer for the TINYCUA prototype: native benchmark tools (shell, file, HTTP, Python execution), a todo list tool, and SDK-compatible tool wrappers. After M1, the prototype can execute sandboxed local tool actions and return structured observations — no agents, graph orchestration, or task state management are required yet. Task state objects (Session, Task tree, TaskResult) and their associated tools are deferred to M2 (issue #71).

Subprojects affected: `tinycua` (tool implementations), `tinycua-sdk` (tool registration interface — already provides `@tool` decorator and `ToolExecutor`).

---

## Architecture

### Component Overview

```
tinycua/tinycua/agent/tools/
├── __init__.py              # Public exports; register_all() convenience
├── native/
│   ├── __init__.py          # Re-exports from individual modules
│   ├── shell.py             # run_shell
│   ├── files.py             # read_file, write_file, edit_file, list_files
│   ├── web.py               # fetch_url
│   └── python_exec.py       # run_python
├── todo/
│   ├── __init__.py          # Re-exports
│   └── todo_list.py         # TodoList tool
└── context.py               # ExecutorContext: shared state for all tools

tinycua-sdk/                 # (existing) @tool decorator, ToolExecutor
```

**Data flow:**

```
Agent (via LLM) 
  → ToolExecutor.execute(tool_name, args) 
    → @tool-decorated function 
      → operates on ExecutorContext (config, TodoList; Session slot reserved for M2)
        → returns JSON-serializable result
```

The `ExecutorContext` acts as the shared state container:

```python
@dataclass
class ExecutorContext:
    session: Session | None = None  # Reserved for M2 — always None in M1
    todo_list: TodoList            # In-memory todo items
    config: ExecutorConfig         # Timeouts, allowed paths, feature flags
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/agent/tools/__init__.py` | Modified | Add exports + `register_all()` |
| `tinycua/agent/tools/native/` | New | Shell, files, web, python exec tools |
| `tinycua/agent/tools/todo/` | New | Todo list tool |
| `tinycua/agent/tools/context.py` | New | ExecutorContext dataclass |
| `tinycua/state/` | M2 (#71) | Session, Task, TaskResult types — NOT YET IMPLEMENTED, deferred to M2 |
| `tinycua-sdk` | Existing (no changes) | `@tool` decorator, `ToolExecutor` consumed as-is |

---

## Data Model

### ExecutorContext

```python
@dataclass
class ExecutorConfig:
    shell_timeout: int = 30
    python_timeout: int = 30
    fetch_timeout: int = 30
    max_file_size: int = 102400           # 100KB
    max_fetch_size: int = 102400          # 100KB
    allowed_paths: list[str] | None = None  # None = no restriction
    enable_fetch: bool = True
    enable_python_exec: bool = True

@dataclass
class ExecutorContext:
    session: Session | None = None
    todo_list: TodoList | None = None
    config: ExecutorConfig = field(default_factory=ExecutorConfig)
```

### Tool Result Shapes

#### Native Tools (shell, files, web, python)

Same shapes as defined in `native_tools/design.md`:
- `run_shell`: `{"stdout": str, "stderr": str, "exit_code": int, "timed_out": bool, "error": str | None}`
- `read_file`: `str` (content) on success; `{"error": str}` on failure
- `write_file`: `{"success": bool, "path": str, "chars_written": int, "error": str | None}`
- `edit_file`: `{"success": bool, "path": str, "start_line": int, "lines_replaced": int, "bytes_written": int, "error": str | None}`
- `list_files`: `list[str]` on success; `{"error": str}` on failure
- `fetch_url`: `str` (body) on success; `{"error": str}` on failure
- `run_python`: `{"stdout": str, "stderr": str, "exit_code": int, "timed_out": bool, "error": str | None}`

#### TodoList Tool

Multi-operation tool using a `command` parameter:

```python
@tool
def todo_list(command: str, item: str | None = None, 
              item_id: int | None = None, status: str | None = None) -> dict | list:
    """Manage the executor-local todo list.
    
    Commands:
    - "add" (item): Add a new todo item. Returns {"success": true, "id": 1, "item": "..."}
    - "list": List all items. Returns [{"id": 1, "item": "...", "status": "pending"}, ...]
    - "update" (item_id, status): Update item status to "pending" or "completed". 
      Returns {"success": true, "id": 1, "status": "completed"}
    - "clear": Remove all items. Returns {"success": true, "cleared_count": 5}
    """
```

---

## API / Interface Contracts

### Tool Factories

To support context injection (no global state), tools are created via factory functions:

```python
# context.py
@dataclass
class ExecutorConfig:
    ...

@dataclass
class ExecutorContext:
    session: Session | None = None
    todo_list: TodoList | None = None
    config: ExecutorConfig = field(default_factory=ExecutorConfig)


# tools/__init__.py
def register_all(context: ExecutorContext | None = None) -> list[Callable]:
    """Return all basic tools with an optional context.
    If context is None, tools will create a default context on first call.
    """
    ...

# Convenience: each tool module exposes a create_<tool>(context) factory.
```

### Tool Signatures

```python
# shell.py
@tool
def run_shell(command: str, timeout: int = 30) -> dict:
    """Execute a shell command and return stdout, stderr, and exit code."""

# files.py
@tool
def read_file(path: str, start: int | None = None, offset: int | None = None) -> str | dict:
    """Read the contents of a file."""

@tool
def write_file(path: str, content: str) -> dict:
    """Write content to a file, creating parent directories if needed."""

@tool
def edit_file(path: str, start: int, content: str, offset: int | None = None) -> dict:
    """Replace lines in an existing file starting at a given line number."""

@tool
def list_files(path: str, pattern: str = "*") -> list[str] | dict:
    """List files in a directory matching a glob pattern."""

# web.py
@tool
def fetch_url(url: str, method: str = "GET", headers: dict | None = None,
              timeout: int = 30, max_size: int = 102400) -> str | dict:
    """Fetch content from a URL."""

# python_exec.py
@tool
def run_python(code: str, timeout: int = 30) -> dict:
    """Execute Python code in a subprocess and return stdout, stderr, and exit code."""

# todo/todo_list.py
@tool
def todo_list(command: str, item: str | None = None,
              item_id: int | None = None, status: str | None = None) -> dict | list:
    """Manage the executor-local todo list."""
```

### Error Handling

| Error Case | Return Value |
|------------|-------------|
| File not found | `{"error": "File not found: ..."}` |
| Directory not found | `{"error": "Directory not found: ..."}` |
| Permission denied | `{"error": "Permission denied: ..."}` |
| Shell command timeout | `{"stdout": "...", "stderr": "...", "exit_code": -1, "timed_out": true}` |
| Python execution error | `{"stdout": "", "stderr": "<traceback>", "exit_code": 1, "timed_out": false}` |
| HTTP error (4xx/5xx) | `{"error": "HTTP 404: Not Found"}` |
| HTTP timeout | `{"error": "Request timed out after 30s"}` |
| Invalid todo command | `{"error": "Unknown todo command: 'xyz'. Valid: add, list, update, clear"}` |
| Todo item not found | `{"error": "Todo item not found: id=42"}` |

---

## Implementation Phases

### Phase 1 — Native Tools (shell, file, HTTP, python)

- [ ] Create `tinycua/agent/tools/context.py` — `ExecutorContext`, `ExecutorConfig`
- [ ] Create `tinycua/agent/tools/native/` package
- [ ] Implement `shell.py` — `run_shell` with subprocess + timeout
- [ ] Implement `files.py` — `read_file`, `write_file`, `edit_file`, `list_files`
- [ ] Implement `web.py` — `fetch_url` using `httpx`
- [ ] Implement `python_exec.py` — `run_python` using subprocess
- [ ] Update `tinycua/agent/tools/__init__.py` with native tool exports
- [ ] Write unit tests for each native tool

### Phase 2 — TodoList Tool

- [ ] Create `tinycua/agent/tools/todo/` package
- [ ] Implement `todo_list.py` — `todo_list` with add/list/update/clear
- [ ] Update `tinycua/agent/tools/__init__.py` with todo tool export
- [ ] Write unit tests for todo list tool

### Phase 3 — Integration & SDK Wrappers

- [ ] Implement `register_all()` in `tools/__init__.py`
- [ ] Write integration tests: register all tools with SDK `Agent`, invoke through `ToolExecutor`

---

## Technical Decisions

1. **Decision**: Use context injection (factory functions) rather than global singletons for tool state.
   - **Reason**: Every tool function needs access to Session state, todo list, and configuration. Global singletons make testing harder (shared state leaks between tests) and prevent running multiple executor instances. Factory functions that capture a context reference allow each tool instance to have its own state.
   - **Alternatives Considered**: Global `ExecutorContext` singleton — simpler but makes parallel execution and test isolation impossible. Thread-local context — unnecessary complexity for prototype. Passing context as a tool parameter — would change the SDK tool interface contract.

2. **Decision**: `TodoList` is a multi-operation tool with a `command` parameter rather than separate tools per operation.
   - **Reason**: Reduces the number of tool registrations. The todo list is a simple utility, not a core workflow concern. A single tool with command routing is easier for the LLM to discover and use.
   - **Alternatives Considered**: Separate `todo_add`, `todo_list`, `todo_update`, `todo_clear` tools — cleaner separation but adds 4 tool registrations for a simple utility.

3. **Decision**: `fetch_url` and `run_python` are feature-gated via `ExecutorConfig.enable_fetch` and `ExecutorConfig.enable_python_exec`.
   - **Reason**: Not all benchmarks require HTTP fetching or code execution. Disabling these tools reduces security surface when they are not needed. Feature flags allow conditional registration without changing tool code.
   - **Alternatives Considered**: Separate registration lists — consumer must know which tools to register. Removing the tools entirely — would require re-adding them when needed.

4. **Decision**: `read_file` uses the same interface as in the `native_tools` spec: full-file mode (with truncation) and range mode (with `start`/`offset` parameters).
   - **Reason**: Consistency with the existing native_tools design. The interface has already been reviewed and addresses the key use cases (quick full reads + targeted line-range reads).

5. **Decision**: Task tree mutations (deferred to M2) should be single-task operations (one add/delete/edit at a time) rather than batch operations.
   - **Reason**: Simpler implementation and testing. Batch operations can be composed from single operations by the agent or orchestrator. Single operations also make it easier to track what changed in the execution log.
   - **Alternatives Considered**: Batch `update_task_tree(operations: list)` — more efficient for bulk changes but harder to validate and log.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `run_shell` could execute dangerous commands | Medium | High | Scope: benchmarks run in controlled environments. Allowed paths and command allowlist in future. |
| `run_python` could have infinite loops | Medium | Medium | Configurable timeout (default 30s) enforced by subprocess kill. |
| Task state corruption from concurrent tool calls | Low | High | Prototype is single-threaded. No concurrent agent calls in M1 scope. |
| `fetch_url` could leak internal network information | Low | Medium | Only HTTP/HTTPS URLs; no file:// or internal IP ranges. Feature-gated by default. |
| Large file reads could exhaust memory | Low | Medium | Internal truncation at 100KB for full-file reads. Agent bypasses limit by setting `start`/`offset`. |

---

## References

- Spec: `./spec.md`
- Related specs: `../native_tools/spec.md`
- Architecture docs: `src/tinycua/docs/architecture/` (state objects documentation deferred to M2)
- Issue: [#70 [Prototype M1]: Basic Tools](https://github.com/VJyzCELERY/TINYCUA/issues/70)
- M2 Tracking: [#71 Data Structures, Entity Relationships, and Rules](https://github.com/VJyzCELERY/TINYCUA/issues/71)
