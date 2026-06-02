# Design Document: M1 — Basic Tools

**Spec**: `specs/tinycua/spec.md`
**Status**: Draft
**Last Updated**: 2026-06-02

---

## Overview

M1 implements the foundational tool layer for the tinycua core library — the executable surface that future Task Executor agents and benchmark automation will call. This includes a unified `ToolResult` model, concrete tools (shell, file, HTTP, Python, task, todo), and wrappers compatible with `tinycua-sdk` tool registration. All tools are structured as stateless callables that receive arguments and return a `ToolResult`, making them testable in isolation and composable into higher-level agent loops.

---

## Architecture

### Component Overview

```
[Caller (Test / Agent / Executor)]
               |
      [Tool.call(arguments)]
               |
    +----------+-----------+
    |      ToolResult      |
    |  - success: bool     |
    |  - output: str       |
    |  - error: str | None |
    |  - metadata: dict    |
    |  - duration: float   |
    +----------+-----------+
               |
    +----------+-----------+
    |   Tool Implementations  |
    |  ShellTool              |
    |  FileReadTool           |
    |  FileWriteTool          |
    |  FileListTool           |
    |  HttpFetchTool          |
    |  PythonExecTool         |
    |  TaskReadTool*          |
    |  TaskWriteTool*         |
    |  TodoListTool           |
    +-------------------------+
               |
    [tinycua-sdk Tool registration]
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.tools.result` | New | `ToolResult` model — success, output, error, metadata, duration |
| `tinycua.tools.base` | New | Base tool protocol/abstract class |
| `tinycua.tools.shell` | New | Shell execution with timeout, stdout/stderr capture |
| `tinycua.tools.file` | New | File read/write/list with allowed-path enforcement |
| `tinycua.tools.web` | New | HTTP fetch tool (if scoped in) |
| `tinycua.tools.python` | New | Python/code execution tool (if scoped in) |
| `tinycua.tools.task` | New | Task read tools: ReadActiveTask, ReadTask, ListTask |
| `tinycua.tools.task_write` | New | Task mutation tools: TaskInit, SetSubTask, AddSubTask, etc. |
| `tinycua.tools.todo` | New | TodoListTool — add/list/update/clear |
| `tinycua.constants.tools` | Modified | Wire new tools into existing `*_BASE_TOOLS` constants |
| `tinycua-sdk` | Reference | Tools implement the `tinycua_sdk.Tool` protocol |

---

## Data Model

### New Entities

```python
# tinycua/tools/result.py

@dataclass
class ToolResult:
    """Structured result from any tool execution."""
    success: bool
    output: str
    error: str | None = None
    metadata: dict = field(default_factory=dict)
    duration: float = 0.0
```

```python
# tinycua/tools/base.py (protocol)

class Tool(Protocol):
    """Protocol matching tinycua_sdk.Tool interface."""
    name: str
    description: str

    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given arguments, return a ToolResult."""
        ...
```

### Schema Changes

- No existing schemas are modified. This is a purely additive layer.
- `ToolResult` is designed to be consumable by the future `ExecutionLog` (see `src/tinycua/docs/design/state/execution_log.md`).

---

## API / Interface Contracts

### New Functions / Tools

```python
# Shell execution
ShellTool(timeout: int = 30) -> Tool
    .execute(command: str) -> ToolResult
    # Raises nothing — errors captured in ToolResult.error
    # Timeout returns ToolResult(success=False, error="Command timed out after Ns")

# File operations
FileReadTool(allowed_paths: list[Path]) -> Tool
    .execute(path: str) -> ToolResult
    # Returns file contents in output
    # Path outside allowed_paths → ToolResult(success=False, error="Path not allowed")

FileWriteTool(allowed_paths: list[Path]) -> Tool
    .execute(path: str, content: str) -> ToolResult
    # Overwrites file content, creates parent dirs if needed
    # Path outside allowed_paths → failure

FileListTool(allowed_paths: list[Path]) -> Tool
    .execute(pattern: str, path: str | None = None) -> ToolResult
    # Glob pattern matching, returns sorted list in output (one per line)
    # Base directory restricted to allowed_paths

# HTTP fetch (if scoped in)
HttpFetchTool(timeout: int = 30) -> Tool
    .execute(url: str, method: str = "GET", headers: dict | None = None) -> ToolResult

# Python execution (if scoped in)
PythonExecTool(timeout: int = 30) -> Tool
    .execute(code: str) -> ToolResult
    # Captures stdout, stderr; sandboxes via restricted globals/locals

# Task read tools
ReadActiveTask(session: Session) -> Tool
    .execute() -> ToolResult
    # Returns current active task JSON in output

ReadTask(session: Session) -> Tool
    .execute(task_id: str) -> ToolResult
    # Returns specific task by ID

ListTask(session: Session) -> Tool
    .execute(status: str | None = None) -> ToolResult
    # Lists all tasks, optionally filtered by status

# Task mutation tools (follow safe re-indexing pattern from design/tools/task.md)
TaskInit(session: Session) -> Tool
    .execute(goal: str) -> ToolResult

SetSubTask(session: Session) -> Tool
    .execute(parent_task_id: str, task_id: str) -> ToolResult

AddSubTask(session: Session) -> Tool
    .execute(parent_task_id: str, title: str) -> ToolResult

DeleteSubTask(session: Session) -> Tool
    .execute(task_id: str) -> ToolResult

EditSubTask(session: Session) -> Tool
    .execute(task_id: str, title: str | None = None, status: str | None = None) -> ToolResult

SwapTask(session: Session) -> Tool
    .execute(task_id_a: str, task_id_b: str) -> ToolResult

UpdateTaskResult(session: Session) -> Tool
    .execute(task_id: str, result: str) -> ToolResult

UpdateActiveTaskResult(session: Session) -> Tool
    .execute(result: str) -> ToolResult

# Todo tool
TodoListTool(session: Session) -> Tool
    .execute(action: str, ...) -> ToolResult
    # actions: "add", "list", "update", "clear"
```

### Error Handling

| Error Case | ToolResult | Notes |
|------------|-----------|-------|
| Shell command not found | `success=False, error="Command not found: ..."` | |
| Shell timeout | `success=False, error="Command timed out after 30s"` | |
| File path outside allowlist | `success=False, error="Path not allowed: ..."` | Security enforcement |
| File not found | `success=False, error="File not found: ..."` | |
| HTTP non-2xx | `success=False, output=<body>, error="HTTP 404"` | |
| Python exec error | `success=False, error=<traceback>` | |
| Task tree invariant violation | `success=False, error="..."` | Safe re-indexing prevents partial failure |
| Todo invalid action | `success=False, error="Unknown action: ..."` | |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] `ToolResult` data model (success, output, error, metadata, duration)
- [ ] Base tool protocol matching `tinycua_sdk.Tool`
- [ ] `ShellTool` — subprocess execution with timeout, stdout/stderr capture
- [ ] `FileReadTool` — read file with path allowlist
- [ ] `FileWriteTool` — write file with path allowlist
- [ ] `FileListTool` — glob/list with path allowlist
- [ ] Task read tools: `ReadActiveTask`, `ReadTask`, `ListTask`
- [ ] Task mutation tools: `TaskInit`, `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, `UpdateTaskResult`, `UpdateActiveTaskResult`
- [ ] `TodoListTool` — add/list/update/clear
- [ ] Wire tools into `tinycua.constants.tools` constants

### Phase 2 — Enhancements _(post-MVP, if spec explicitly requires HTTP/Python)_

- [ ] `HttpFetchTool` — GET/HEAD with timeout, optional headers
- [ ] `PythonExecTool` — code execution with sandboxed globals/locals

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: `ToolResult` as a single dataclass rather than separate `SuccessResult`/`FailureResult` types.
   - **Reason**: Simpler API surface; consumers always handle the same shape. The `success` boolean discriminates outcome.
   - **Alternatives Considered**: Union types (`SuccessResult | FailureResult`) — rejected because it complicates consumer code without benefit at this layer.

2. **Decision**: Stateless tool instances with explicit session injection for stateful tools.
   - **Reason**: Tools become pure argument-in → ToolResult-out functions. Session state is externalized, making tools testable without mocking global state.
   - **Alternatives Considered**: Stateful tools holding internal references — rejected because it complicates lifecycle management and testing.

3. **Decision**: File tools enforce path allowlists at construction time.
   - **Reason**: Security boundary is explicit per-tool instance. Different callers can have different allowed scopes.
   - **Alternatives Considered**: Global allowlist — rejected because it lacks granularity.

4. **Decision**: Task tools follow the existing safe re-indexing pattern from `design/tools/task.md`.
   - **Reason**: Prevents malformed task tree indices on partial failures. Already designed and documented.
   - **Alternatives Considered**: No re-indexing — rejected because partial mutations would leave invalid state.

5. **Decision**: `TodoListTool` uses `session` state rather than a separate store.
   - **Reason**: Todos are session-scoped and should be serialized/restored with session state. No need for a separate persistence layer at this stage.

6. **Decision**: Tool results shaped for `ExecutionLog` consumption.
   - **Reason**: Future `ExecutionLog` entries will reference tool results. Matching the shape now prevents retrofitting later.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Shell tool allows dangerous commands | Medium | High | Document security boundary; path allowlist + command allowlist/denylist |
| File tool path traversal bypass | Low | High | Canonicalize paths via `Path.resolve()` before allowlist check |
| Task tool race conditions (concurrent mutation) | Low | Medium | Task tools operate on `session.task` which is replaced atomically; concurrency model is single-threaded within a session |
| Python exec tool sandbox escape | Medium | High | Use `eval`/`exec` with restricted globals; consider running in subprocess with seccomp/firejail for production |
| Tool registration incompatible with tinycua-sdk | Low | High | Implement tools against `tinycua_sdk.Tool` protocol from day one; integration test during Phase 1 |

---

## Open Questions _(optional)_

1. Should `HttpFetchTool` and `PythonExecTool` be included in M1 or deferred to #78?
   - Current thinking: Include only if the selected benchmark subset requires them. The spec has an open question on this.

---

## References

- Spec: `./spec.md` — relative path from this design.md
- [Task Tools Design](../../src/tinycua/docs/design/tools/task.md) — safe re-indexing pattern for task mutations
- [Tool Constants](../../src/tinycua/docs/design/constants/tools.md) — `*_BASE_TOOLS` wiring
- [Todo Tool Design](../../src/tinycua/docs/design/tools/todo.md) — todo operations
- [Digester Tool Interface](../../src/tinycua/docs/design/tools/digester.md) — retrieval tool contract
- [Execution Log Design](../../src/tinycua/docs/design/state/execution_log.md) — tool result consumer shape
- [Task State Design](../../src/tinycua/docs/design/state/task.md) — task tree model (tool-facing behavior only)
