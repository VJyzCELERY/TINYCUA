# Design Document: M1 — Basic Tools

**Spec**: `specs/tinycua-sdk/spec.md`
**Status**: Draft
**Last Updated**: 2026-06-02

---

## Overview

Implement the basic tool layer for tinycua. This layer provides native sandboxed tools (shell, file, task, todo, digester) and a structured `ToolResult` model, all compatible with `tinycua-sdk` tool registration. The implementation covers the tool-facing behavior of task state and execution log models without the full durable persistence layer. Subprojects affected: `tinycua-sdk` (tool wrappers, result model) and `tinycua` (tool implementations, state access).

---

## Architecture

### Component Overview

```
[Caller/Task Executor] --> [tinycua-sdk Tool Registration]
                                    |
                         [Tool Implementations in tinycua]
                                    |
                    +---------------+---------------+
                    |               |               |
              ShellTool      FileTools        TaskTools
                    |               |               |
              subprocess     path check      task state
                    |               |               |
              stdout/stderr   file I/O       tree ops
```

Tool implementations live in `src/tinycua/tinycua/tools/` (or equivalent). Tool wrappers and the result model live in `src/tinycua-sdk/tinycua_sdk/`. The SDK provides the registration interface; `tinycua` provides the concrete implementations.

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_sdk/models/result.py` | New | `ToolResult` model — success/failure, output, error, metadata, duration |
| `tinycua/tools/` | New | Directory for all native tool implementations |
| `tinycua/tools/shell.py` | New | Shell execution tool with timeout |
| `tinycua/tools/file.py` | New | File read/write/list tools with path enforcement |
| `tinycua/tools/http.py` | New | HTTP fetch tool (if required) |
| `tinycua/tools/code_exec.py` | New | Code execution tool (if required) |
| `tinycua/tools/task_tools.py` | New | Task read/mutation tools |
| `tinycua/tools/todo.py` | New | TodoList tool |
| `tinycua/constants/tools.py` | New | Tool name/parameter constants |
| `tinycua_sdk/providers/registry.py` | Modified | Register new tools if needed |

---

## Data Model

### New Entities

```python
# Conceptual data shape
class ToolResult:
    success: bool           # Whether the tool execution succeeded
    output: str             # Primary output (stdout for shell, file contents, etc.)
    error: Optional[str]    # Error message on failure
    metadata: dict          # Additional info (exit code, file size, etc.)
    duration: float         # Execution duration in seconds
```

### Tool Input Shapes

```python
# ShellTool
class ShellInput:
    command: str            # Shell command to execute
    timeout: int = 30       # Timeout in seconds
    workdir: Optional[str]  # Working directory (optional)

# FileReadTool
class FileReadInput:
    path: str               # Path to read (relative to allowed base)
    
# FileWriteTool
class FileWriteInput:
    path: str               # Path relative to allowed base
    content: str            # Content to write

# FileListTool
class FileListInput:
    pattern: str            # Glob pattern

# TaskInit
class TaskInitInput:
    task_id: str
    title: str
    parent_id: Optional[str]

# TodoList
class TodoListInput:
    action: str             # "add" | "list" | "update" | "clear"
    item: Optional[str]
    index: Optional[int]
```

---

## API / Interface Contracts

### Tool Registration Interface

```python
# tinycua_sdk tool registration pattern (existing pattern)
def register_tool(name: str, handler: Callable) -> None: ...

# All M1 tools must follow this pattern:
async def shell_tool_handler(input: ShellInput) -> ToolResult: ...
async def file_read_handler(input: FileReadInput) -> ToolResult: ...
async def file_write_handler(input: FileWriteInput) -> ToolResult: ...
async def file_list_handler(input: FileListInput) -> ToolResult: ...
async def task_init_handler(input: TaskInitInput) -> ToolResult: ...
# ... etc.
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Shell command fails | `ToolResult(success=False, error=<stderr>)` | |
| Shell timeout | `ToolResult(success=False, error="Timeout after Ns")` | Process is killed |
| File path outside allowed | `ToolResult(success=False, error="Path not allowed")` | |
| File not found | `ToolResult(success=False, error="File not found")` | |
| Invalid task operation | `ToolResult(success=False, error=<description>)` | |
| Invalid todo action | `ToolResult(success=False, error="Invalid action")` | |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Define `ToolResult` model in `tinycua_sdk/models/result.py`
- [ ] Implement shell execution tool with timeout
- [ ] Implement file read/write/list tools with path enforcement
- [ ] Implement task read tools: `ReadActiveTask`, `ReadTask`, `ListTask`
- [ ] Implement task mutation tools: `TaskInit`, `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, `UpdateTaskResult`, `UpdateActiveTaskResult`
- [ ] Implement TodoList tool
- [ ] Define tool constants/mappings
- [ ] Write unit tests for all tools
- [ ] Verify tests pass: `cd src/tinycua && uv run pytest tests/test_tools* tests/test_task_tools* tests/test_todo*`

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Implement HTTP fetch tool (if required by selected benchmark subset)
- [ ] Implement code execution tool (if required by selected benchmark subset)
- [ ] Full browser/GUI automation adapter contract (if required)
- [ ] Tool result persistence

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use `subprocess` with `timeout` for shell execution rather than a full sandbox.
   - **Reason**: Simplest approach; full sandboxing (seccomp, container) is out of scope for M1.
   - **Alternatives Considered**: Docker containers — rejected due to complexity and dependency requirements.

2. **Decision**: Tool implementations live in `tinycua` package, with the result model in `tinycua-sdk`.
   - **Reason**: The SDK provides the interface contract; `tinycua` provides concrete implementations. This separation allows the SDK to remain lightweight.
   - **Alternatives Considered**: All in SDK — rejected because tools have dependencies (subprocess, file I/O) that belong in the main package.

3. **Decision**: Path enforcement uses a configurable allowed base directory with no traversal above it.
   - **Reason**: Simple and effective for sandboxing file operations in the prototype.
   - **Alternatives Considered**: Full path allowlist/denylist — overkill for M1.

4. **Decision**: Task tools operate on an in-memory task tree (no persistence for M1).
   - **Reason**: Durable persistence is explicitly out of scope for M1.
   - **Alternatives Considered**: Database-backed — deferred to later milestone.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Shell command injection | Medium | High | Restrict to single commands, no shell piping; path restrictions on file args |
| File path traversal | Medium | High | Enforce allowed base directory; reject paths with `../` |
| Timeout not killing process | Low | Medium | Use `process.kill()` after timeout; verify in tests |
| Tool registration incompatible with SDK | Low | High | Follow existing `tinycua_sdk` registration pattern; verify with integration test |

---

## Open Questions _(optional)_

1. Should HTTP fetch and code execution tools be part of M1 or deferred to a later milestone?
   - **Current thinking**: Defer to Phase 2 unless the selected benchmark subset explicitly requires them.

2. Where exactly should the allowed base directory for file tools be configured?
   - **Current thinking**: A constant or environment variable in `tinycua/config.py` or similar.

---

## References

- Spec: `specs/tinycua-sdk/spec.md`
- Existing tool design docs:
  - `src/tinycua/docs/design/tools/task.md`
  - `src/tinycua/docs/design/tools/todo.md`
  - `src/tinycua/docs/design/tools/digester.md`
  - `src/tinycua/docs/design/constants/tools.md`
- Existing state design docs (tool-facing):
  - `src/tinycua/docs/design/state/task.md`
  - `src/tinycua/docs/design/state/execution_log.md`
- GitHub Issue: [#70 — [Prototype M1]: Basic Tools](https://github.com/VJyzCELERY/TINYCUA/issues/70)
