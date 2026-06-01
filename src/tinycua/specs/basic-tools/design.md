# Design Document: Prototype M1 — Basic Tools

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-02

---

## Overview

Implement the complete basic tool layer for the TINYCUA prototype: native benchmark tools (shell, file, HTTP, Python execution), task state read/mutation tools, a todo list tool, and SDK-compatible tool wrappers. After M1, the prototype can execute sandboxed local tool actions and return structured observations — no agents or graph orchestration are required yet.

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
├── task/
│   ├── __init__.py          # Re-exports
│   ├── readers.py           # ReadActiveTask, ReadTask, ListTask
│   └── mutators.py          # TaskInit, SetSubTask, AddSubTask, DeleteSubTask,
│                            #   EditSubTask, SwapTask, UpdateTaskResult,
│                            #   UpdateActiveTaskResult
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
      → operates on ExecutorContext (Session, TodoList, config)
        → returns JSON-serializable result
```

The `ExecutorContext` acts as the shared state container:

```python
@dataclass
class ExecutorContext:
    session: Session | None        # Current session (holds task tree)
    todo_list: TodoList            # In-memory todo items
    config: ExecutorConfig         # Timeouts, allowed paths, feature flags
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/agent/tools/__init__.py` | Modified | Add exports + `register_all()` |
| `tinycua/agent/tools/native/` | New | Shell, files, web, python exec tools |
| `tinycua/agent/tools/task/` | New | Task read/mutation tools |
| `tinycua/agent/tools/todo/` | New | Todo list tool |
| `tinycua/agent/tools/context.py` | New | ExecutorContext dataclass |
| `tinycua/state/` | Existing | Session, Task, TaskResult types — already implemented |
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

#### Task Tools

`ReadActiveTask`:
```python
# Returns the currently active task's Task node as a dict.
# On success: {task_id, task_name, task_description, task_context, success_criteria,
#              confidence, task_result: {...} | None, child_tasks: [...] | None}
# On no active task: {"error": "No active task set"}
```

`ReadTask`:
```python
# Returns a specific task by task_id string.
# On success: {task_id, task_name, ...} (same shape as ReadActiveTask)
# On not found: {"error": "Task not found: T-1.2"}
```

`ListTask`:
```python
# Returns a flattened list of all tasks with status markers.
# [
#   {"id": "T-1", "name": "...", "status": "not_started", "depth": 0},
#   {"id": "T-1.1", "name": "...", "status": "completed", "depth": 1},
#   ...
# ]
```

`TaskInit`:
```python
# Creates a new task tree from a list of top-level tasks.
# Returns: {"success": true, "active_task_id": "T-1"}
# On already active: {"error": "Task already active. Use UpdateTaskResult or close current task first."}
#   (or optionally replaces if force=True param is set)
```

`SetSubTask`:
```python
# Replaces child_tasks of a given parent with a new list.
# Returns: {"success": true, "task_id": "T-1", "child_count": 3}
# On not found: {"error": "Task not found: T-1"}
```

`AddSubTask`:
```python
# Appends a new child task under a parent.
# Returns: {"success": true, "child_task_id": "T-1.4"}
```

`DeleteSubTask`:
```python
# Removes a child task by ID from its parent.
# Returns: {"success": true, "deleted_task_id": "T-1.2"}
# Deletion is recursive: if the deleted task has children, they are also removed.
```

`EditSubTask`:
```python
# Updates editable fields on a task (name, description, context, success_criteria, confidence).
# Returns: {"success": true, "task_id": "T-1.2", "updated_fields": [...]}
```

`SwapTask`:
```python
# Swaps the order of two child tasks within the same parent.
# Returns: {"success": true, "task_id_1": "T-1.1", "task_id_2": "T-1.2"}
```

`UpdateTaskResult`:
```python
# Sets task_result on a specific task.
# Returns: {"success": true, "task_id": "T-1.2", "status": "completed"}
```

`UpdateActiveTaskResult`:
```python
# Sets task_result on the currently active task.
# Returns: {"success": true, "task_id": "T-1", "status": "completed"}
```

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

# task/readers.py
@tool
def read_active_task() -> dict:
    """Return the currently active task's data."""

@tool
def read_task(task_id: str) -> dict:
    """Return a specific task by ID."""

@tool
def list_task() -> list[dict]:
    """List all tasks with status markers."""

# task/mutators.py
@tool
def task_init(tasks: list[dict], force: bool = False) -> dict:
    """Create a new task tree from a list of top-level task configs."""

@tool
def set_sub_task(task_id: str, children: list[dict]) -> dict:
    """Replace child tasks of a given parent."""

@tool
def add_sub_task(task_id: str, task: dict) -> dict:
    """Append a child task under a parent."""

@tool
def delete_sub_task(task_id: str, parent_id: str) -> dict:
    """Remove a child task from its parent."""

@tool
def edit_sub_task(task_id: str, **fields) -> dict:
    """Update editable fields on a task."""

@tool
def swap_task(parent_id: str, task_id_1: str, task_id_2: str) -> dict:
    """Swap the order of two child tasks."""

@tool
def update_task_result(task_id: str, status: str, result: str | None = None) -> dict:
    """Set the result on a specific task."""

@tool
def update_active_task_result(status: str, result: str | None = None) -> dict:
    """Set the result on the currently active task."""

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
| Task not found | `{"error": "Task not found: T-1.2"}` |
| No active task | `{"error": "No active task set"}` |
| Task already active | `{"error": "Task already active. Use force=True to replace."}` |
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

### Phase 2 — Task State Tools (readers + mutators)

- [ ] Create `tinycua/agent/tools/task/` package
- [ ] Implement `readers.py` — `read_active_task`, `read_task`, `list_task`
- [ ] Implement `mutators.py` — `task_init`, `set_sub_task`, `add_sub_task`, `delete_sub_task`, `edit_sub_task`, `swap_task`, `update_task_result`, `update_active_task_result`
- [ ] Update `tinycua/agent/tools/__init__.py` with task tool exports
- [ ] Write unit tests for each task tool

### Phase 3 — TodoList Tool

- [ ] Create `tinycua/agent/tools/todo/` package
- [ ] Implement `todo_list.py` — `todo_list` with add/list/update/clear
- [ ] Update `tinycua/agent/tools/__init__.py` with todo tool export
- [ ] Write unit tests for todo list tool

### Phase 4 — Integration & SDK Wrappers

- [ ] Implement `register_all()` in `tools/__init__.py`
- [ ] Write integration tests: register all tools with SDK `Agent`, invoke through `ToolExecutor`
- [ ] Write end-to-end test: multi-step task workflow (init → add subtask → read → update result)

---

## Technical Decisions

1. **Decision**: Use context injection (factory functions) rather than global singletons for tool state.
   - **Reason**: Every tool function needs access to Session state, todo list, and configuration. Global singletons make testing harder (shared state leaks between tests) and prevent running multiple executor instances. Factory functions that capture a context reference allow each tool instance to have its own state.
   - **Alternatives Considered**: Global `ExecutorContext` singleton — simpler but makes parallel execution and test isolation impossible. Thread-local context — unnecessary complexity for prototype. Passing context as a tool parameter — would change the SDK tool interface contract.

2. **Decision**: `TodoList` is a multi-operation tool with a `command` parameter rather than separate tools per operation.
   - **Reason**: Reduces the number of tool registrations. The todo list is a simple utility, not a core workflow concern. A single tool with command routing is easier for the LLM to discover and use.
   - **Alternatives Considered**: Separate `todo_add`, `todo_list`, `todo_update`, `todo_clear` tools — cleaner separation but adds 4 tool registrations for a simple utility.

3. **Decision**: Task tools operate on `Session.task_tree` directly rather than maintaining a separate task store.
   - **Reason**: The `Session` object is already the canonical container for task state. The state objects spec already defines `Task`, `TaskResult`, and traversal methods (`traverse()`, `at_id()`). Reusing these types avoids duplication and keeps the architecture consistent.
   - **Alternatives Considered**: Separate in-memory task store — would duplicate state and require synchronization with Session.

4. **Decision**: `fetch_url` and `run_python` are feature-gated via `ExecutorConfig.enable_fetch` and `ExecutorConfig.enable_python_exec`.
   - **Reason**: Not all benchmarks require HTTP fetching or code execution. Disabling these tools reduces security surface when they are not needed. Feature flags allow conditional registration without changing tool code.
   - **Alternatives Considered**: Separate registration lists — consumer must know which tools to register. Removing the tools entirely — would require re-adding them when needed.

5. **Decision**: `read_file` uses the same interface as in the `native_tools` spec: full-file mode (with truncation) and range mode (with `start`/`offset` parameters).
   - **Reason**: Consistency with the existing native_tools design. The interface has already been reviewed and addresses the key use cases (quick full reads + targeted line-range reads).

6. **Decision**: Task tree mutations are single-task operations (one add/delete/edit at a time) rather than batch operations.
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
| Task tree IDs become inconsistent after deletions | Low | Medium | ID assignment is sequential and non-reusable. Deletion removes subtrees cleanly. Test coverage for edge cases. |

---

## References

- Spec: `./spec.md`
- Related specs: `../native_tools/spec.md`, `../state-objects/spec.md`
- Architecture docs: `src/tinycua/docs/architecture/state-objects.md`, `src/tinycua/docs/architecture/session-architecture.md`
- Issue: [#70 [Prototype M1]: Basic Tools](https://github.com/VJyzCELERY/TINYCUA/issues/70)
