# Implementation: Prototype M1 — Basic Tools

Implement the basic tool layer for the TINYCUA prototype: native benchmark tools (shell, file, HTTP, Python execution), a todo list tool, SDK-compatible tool wrappers, and a shared executor context. After M1, the prototype can execute sandboxed local tool actions and return structured observations.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P0
- **Estimated Effort**: M

## Environment Pre-requisites

> **N/A** — This implementation requires no special environment setup beyond what is already configured for the `tinycua` subproject. The existing dev dependencies (pytest, httpx, etc.) are sufficient.

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

### Integration Test: Full SDK Registration & Execution

```python
# Test file: src/tinycua/tests/test_tools_integration.py
"""Integration tests for basic tools — SDK registration and execution."""

from tinycua.agent.tools import register_all


def test_register_all_returns_all_tools():
    """register_all() should return a list of all basic tool functions."""
    tools = register_all()
    tool_names = {t.__name__ for t in tools}
    assert "run_shell" in tool_names
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "edit_file" in tool_names
    assert "list_files" in tool_names
    assert "fetch_url" in tool_names
    assert "run_python" in tool_names
    assert "todo_list" in tool_names


def test_tools_work_through_sdk_executor(tmp_path):
    """Tools should be invocable through the SDK's ToolExecutor."""
    from tinycua.agent.tools import register_all
    from tinycua_sdk.executor import ToolExecutor

    tools = register_all()
    executor = ToolExecutor(tools=tools)

    # Write a file and read it back
    test_file = tmp_path / "hello.txt"
    write_result = executor.execute("write_file", {"path": str(test_file), "content": "Hello, World!"})
    assert write_result["success"] is True

    read_result = executor.execute("read_file", {"path": str(test_file)})
    assert "Hello, World!" in read_result

    # Edit the file
    edit_result = executor.execute("edit_file", {
        "path": str(test_file),
        "start": 1,
        "content": "Edited line"
    })
    assert edit_result["success"] is True
    assert edit_result["lines_replaced"] >= 1

    # List files (covers spec.md Acceptance Scenario 4)
    list_result = executor.execute("list_files", {"path": str(tmp_path), "pattern": "*.txt"})
    assert "hello.txt" in list_result
```

### Integration Test: Todo List Operations

```python
def test_todo_list_full_workflow():
    """Todo list add/list/update/clear should work as a full workflow."""
    from tinycua.agent.tools import register_all

    tools = register_all()
    todo_tool = next(t for t in tools if t.__name__ == "todo_list")

    # Add items
    r1 = todo_tool(command="add", item="First task")
    assert r1["success"] is True
    assert r1["id"] == 1

    r2 = todo_tool(command="add", item="Second task")
    assert r2["id"] == 2

    # List items
    items = todo_tool(command="list")
    assert len(items) == 2

    # Update first item to completed
    update_r = todo_tool(command="update", item_id=1, status="completed")
    assert update_r["success"] is True

    # Clear
    clear_r = todo_tool(command="clear")
    assert clear_r["success"] is True
    assert clear_r["cleared_count"] == 2

    items_after = todo_tool(command="list")
    assert len(items_after) == 0
```

### Integration Test: Context Injection

```python
def test_context_injection():
    """Tools created with a shared context should share state."""
    from tinycua.agent.tools.context import ExecutorContext, ExecutorConfig
    from tinycua.agent.tools import register_all

    config = ExecutorConfig(shell_timeout=10, enable_fetch=False)
    ctx = ExecutorContext(config=config)
    tools = register_all(context=ctx)

    # Tools bound to this context should use the config
    # (verified by checking the context reference in the closure)
    todo_tool = next(t for t in tools if t.__name__ == "todo_list")
    todo_tool(command="add", item="Context test")
    items = todo_tool(command="list")
    assert len(items) == 1
    assert items[0]["item"] == "Context test"
```

### Integration Test: Timeout Enforcement

```python
def test_shell_timeout_enforcement():
    """A shell command exceeding the configured timeout should be killed."""
    from tinycua.agent.tools.context import ExecutorContext, ExecutorConfig
    from tinycua.agent.tools import register_all

    config = ExecutorConfig(shell_timeout=1)
    ctx = ExecutorContext(config=config)
    tools = register_all(context=ctx)

    shell_tool = next(t for t in tools if t.__name__ == "run_shell")
    # timeout=30 exceeds shell_timeout=1 → should be clamped to 1
    result = shell_tool(command="sleep 10", timeout=30)
    assert result["timed_out"] is True
    assert result["exit_code"] == -1


def test_timeout_is_clamped_by_context_config():
    """Tool timeout parameter should be clamped to context config max."""
    from tinycua.agent.tools.context import ExecutorContext, ExecutorConfig
    from tinycua.agent.tools import register_all

    config = ExecutorConfig(shell_timeout=2)
    ctx = ExecutorContext(config=config)
    tools = register_all(context=ctx)

    shell_tool = next(t for t in tools if t.__name__ == "run_shell")
    result = shell_tool(command="sleep 10", timeout=30)
    assert result["timed_out"] is True
    assert result["exit_code"] == -1


def test_timeout_parameter_underrides_context():
    """Tool timeout below the context config should be respected (not clamped up)."""
    from tinycua.agent.tools.context import ExecutorContext, ExecutorConfig
    from tinycua.agent.tools import register_all

    config = ExecutorConfig(shell_timeout=30)
    ctx = ExecutorContext(config=config)
    tools = register_all(context=ctx)

    shell_tool = next(t for t in tools if t.__name__ == "run_shell")
    # timeout=1 is below shell_timeout=30 → should NOT be clamped, should actually time out
    result = shell_tool(command="sleep 10", timeout=1)
    assert result["timed_out"] is True
    assert result["exit_code"] == -1
```

### Integration Test: Feature Gating

```python
def test_feature_flags_disable_tools():
    """Disabling a feature flag should make the corresponding tool unavailable."""
    from tinycua.agent.tools.context import ExecutorContext, ExecutorConfig
    from tinycua.agent.tools import register_all

    config = ExecutorConfig(enable_fetch=False, enable_python_exec=False)
    ctx = ExecutorContext(config=config)
    tools = register_all(context=ctx)

    fetch_tool = next(t for t in tools if t.__name__ == "fetch_url")
    result = fetch_tool(url="http://placeholder.local/not-reached")
    assert "error" in result or "disabled" in result

    python_tool = next(t for t in tools if t.__name__ == "run_python")
    result = python_tool(code="print('hello')")
    assert "error" in result or "disabled" in result
```

### Key Test Scenarios

- **Scenario 1** (covered by integration test above): All 8 tools (7 native + 1 todo) are returned by `register_all()`
- **Scenario 2** (covered by integration test above): Native tools work through the SDK `ToolExecutor` (write + read + edit round-trip)
- **Scenario 3** (covered by integration test above): Todo list full workflow (add, list, update, clear)
- **Scenario 4** (covered by integration test above): Context injection works — tools created with a shared `ExecutorContext` share state
- **Scenario 5** (covered by integration test above): Timeout enforcement — a shell command exceeding the configured timeout is killed; conflict between tool `timeout` and `shell_timeout` resolved by clamping to config max
- **Scenario 6** (covered by integration test above): Feature gating — disabling `enable_fetch`/`enable_python_exec` prevents the corresponding tools from working
- **Scenario 7** (covered by integration test above): Low timeout in tool parameter is respected when below context config (no upward clamping)

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for `ExecutorContext` and `ExecutorConfig` dataclasses
- [ ] Unit tests for `TodoList` — add, list, update, clear, edge cases
- [ ] Unit tests for each native tool — verify they still work individually
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] N/A — tools are deterministic and fully testable in code

### Performance Considerations

- [ ] N/A — no performance-sensitive paths introduced

## Proposed Changes

### Module/Section Name

#### [NEW] `tinycua/agent/tools/context.py`

- **Description**: Create `ExecutorConfig` and `ExecutorContext` dataclasses as the shared state container for all tools.
- **Rationale**: Every tool function needs access to configuration (timeouts, allowed paths, feature flags), the todo list, and a reserved slot for Session state (M2). Context injection avoids global state and makes testing easier.

**ExecutorConfig fields**:
  - `shell_timeout: int = 30`
  - `python_timeout: int = 30`
  - `fetch_timeout: int = 30`
  - `max_file_size: int = 102400` (100KB)
  - `max_fetch_size: int = 102400` (100KB)
  - `allowed_paths: list[str] | None = None`
  - `enable_fetch: bool = True`
  - `enable_python_exec: bool = True`

**ExecutorContext fields**:
  - `session: Session | None = None` (reserved for M2)
  - `todo_list: TodoList | None = None`
  - `config: ExecutorConfig`

#### [NEW] `tinycua/agent/tools/todo/` package

- **Description**: Create the `todo/` subpackage with `__init__.py` and `todo_list.py`.
- **Rationale**: The TodoList is a multi-operation tool (add/list/update/clear) that lives in its own category, separate from native tools (shell, file, web, python).

#### [NEW] `tinycua/agent/tools/todo/__init__.py`

- **Description**: Re-export `todo_list` from `todo_list.py`.

#### [NEW] `tinycua/agent/tools/todo/todo_list.py`

- **Description**: Implement the `todo_list` tool as a `@tool`-decorated function with `command` parameter routing.
- **Commands**: `add` (add item, returns id), `list` (return all items), `update` (set status), `clear` (remove all items).
- **Dependencies**: `ExecutorContext` for accessing the shared todo list.

#### [MODIFY] `tinycua/agent/tools/__init__.py`

- **Description**: Add `register_all()` function that returns all basic tools with optional context injection. Add `TodoList` import and export.
- **Rationale**: Consumers need a single entry point to register all basic tools at once (FR-014).

#### [MODIFY] `tinycua/agent/tools/native/shell.py`

- **Description**: Update `run_shell` to accept and use an `ExecutorContext` for `shell_timeout` configuration, while maintaining backward compatibility (default timeout if no context).
- **Rationale**: Tools should be configurable via the shared context (FR-009).

#### [MODIFY] `tinycua/agent/tools/native/files.py`

- **Description**: Update file tools to use `ExecutorContext` for `max_file_size` and `allowed_paths` configuration, while maintaining backward compatibility.
- **Rationale**: File tools should respect the shared configuration (max file size for truncation, allowed path boundaries).

#### [MODIFY] `tinycua/agent/tools/native/web.py`

- **Description**: Update `fetch_url` to use `ExecutorContext` for `fetch_timeout`, `max_fetch_size`, and `enable_fetch` feature flag, while maintaining backward compatibility.
- **Rationale**: HTTP fetching should respect feature gates and shared config (FR-006).

#### [MODIFY] `tinycua/agent/tools/native/python_exec.py`

- **Description**: Update `run_python` to use `ExecutorContext` for `python_timeout` and `enable_python_exec` feature flag, while maintaining backward compatibility.
- **Rationale**: Python execution should respect feature gates and shared timeout config (FR-007).

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/agent/tools/context.py` | New | `ExecutorConfig` + `ExecutorContext` dataclasses |
| `tinycua/agent/tools/todo/` | New | Todo list tool package |
| `tinycua/agent/tools/__init__.py` | Modify | Add `register_all()`, todo exports |
| `tinycua/agent/tools/native/shell.py` | Modify | Context-aware timeout |
| `tinycua/agent/tools/native/files.py` | Modify | Context-aware max_file_size, allowed_paths |
| `tinycua/agent/tools/native/web.py` | Modify | Context-aware fetch_timeout, max_fetch_size, feature flag |
| `tinycua/agent/tools/native/python_exec.py` | Modify | Context-aware python_timeout, feature flag |

## Data Model Changes

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
    session: Session | None = None        # Reserved for M2
    todo_list: TodoList | None = None     # In-memory todo items
    config: ExecutorConfig = field(default_factory=ExecutorConfig)
```

Todo list item shape:
```python
{
    "id": int,
    "item": str,
    "status": str,  # "pending" | "completed"
}
```

## API Changes

### New Functions

| Function | Module | Description |
|----------|--------|-------------|
| `register_all(context=None)` | `tinycua/agent/tools/__init__` | Return all basic tools with optional context |
| `todo_list(command, item, item_id, status)` | `tinycua/agent/tools/todo/todo_list` | Manage executor-local todo list |

### Modified Functions

| Function | Change |
|----------|--------|
| `run_shell` | Accepts context for configurable timeout (backward-compatible) |
| `read_file` | Accepts context for configurable truncation limit (backward-compatible) |
| `write_file` | Accepts context for allowed_paths check (backward-compatible) |
| `edit_file` | Accepts context for allowed_paths check (backward-compatible) |
| `list_files` | Accepts context for allowed_paths check (backward-compatible) |
| `fetch_url` | Accepts context for timeout, max_size, feature flag (backward-compatible) |
| `run_python` | Accepts context for timeout, feature flag (backward-compatible) |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `tinycua-sdk` | >=0.1.0 | `@tool` decorator, `ToolExecutor` (already exists) |
| `httpx` | >=0.27.0 | HTTP fetching (already exists) |

### Internal Dependencies

- [ ] Depends on `tinycua-sdk`'s `@tool` decorator and `ToolExecutor`
- [ ] Depends on `native_tools` implementation (FR-001–FR-009 from `native_tools/spec.md`) — native tools must exist before M1 modifications begin
- [ ] Does NOT block any other features
- [ ] Does NOT depend on M2 (state objects) — Session slot reserved as `None`

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing native tool signatures | High | Native tool signatures remain unchanged; context is injected via factory closures, not as a parameter |
| Context injection changes add complexity | Medium | Simple pattern: tools are wrapped in factory functions that capture the context; default context created if none provided |
| Todo list state not shared correctly across tools | Medium | The `register_all(context)` function ensures all tools receive the same `ExecutorContext` instance; unit tests verify shared state |
| Feature flags accidentally disable tools during tests | Low | Default config has all features enabled; tests explicitly create configs when testing disabled states |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-02*
