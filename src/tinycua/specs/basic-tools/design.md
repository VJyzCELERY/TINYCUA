# Design Document: M1 — Basic Tools

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-02

---

## Overview

M1 (Basic Tools) implements the entire foundational tool layer for the TINYCUA prototype. This includes native execution tools (shell, file, web, python), task tree read/write tools, a TodoList tool, a digester retrieval tool interface, and the tool constants/mappings that wire them into agent nodes. All tools are implemented as `tinycua_sdk` `@tool`-decorated functions. Together they form the executable surface that every agent node will use.

**Subprojects affected**: `tinycua`

---

## Architecture

### Component Overview

```
tinycua/tinycua/
├── tools/
│   ├── __init__.py              # Public exports (all tool functions + ToolResult)
│   ├── result.py                # Native ToolResult model
│   ├── native/
│   │   ├── __init__.py          # Re-exports from individual modules
│   │   ├── shell.py             # run_shell
│   │   ├── files.py             # read_file, write_file, list_files
│   │   ├── web.py               # fetch_url
│   │   └── python_exec.py       # run_python
│   ├── task/
│   │   ├── __init__.py          # Re-exports
│   │   ├── read.py              # ReadActiveTask, ReadTask, ListTask
│   │   ├── write.py             # TaskInit, SetSubTask, AddSubTask, DeleteSubTask,
│   │   │                        #   EditSubTask, SwapTask, UpdateTaskResult, UpdateActiveTaskResult
│   │   └── _mutation.py         # _apply_task_mutation, _reindex_tree, _remove_by_id,
│   │                            #   _collect_ids, _find_parent_and_child, _is_ancestor (internal helpers)
│   ├── todo.py                  # TodoList tool
│   └── digester.py              # enhanced_context_retrieval, digest_information
├── constants/
│   └── tools.py                 # *_BASE_TOOLS constants for all agent nodes
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/agent/tools/native/` | Existing | Shell, file, web, python tools already exist from native_tools spec — verify SDK compatibility |
| `tinycua/agent/tools/__init__.py` | Modified | Update exports to include all new tools |
| `tinycua/tools/` | New | New top-level package for tool implementations (separate from agent glue) |
| `tinycua/tools/result.py` | New | Native ToolResult dataclass |
| `tinycua/tools/task/` | New | Task read/write tools with re-indexing mutation helpers |
| `tinycua/tools/todo.py` | New | TodoList tool with sub-command dispatch |
| `tinycua/tools/digester.py` | New | enhanced_context_retrieval + digest_information |
| `tinycua/constants/tools.py` | New | *_BASE_TOOLS constant definitions |

**Design docs addressed** (under `docs/design/`):
- `docs/design/tools/task.md` — Task tool specifications
- `docs/design/tools/todo.md` — TodoList tool specification
- `docs/design/tools/digester.md` — Digester tool interface
- `docs/design/constants/tools.md` — Tool constant mappings
- `docs/design/state/task.md` — Task/TaskResult data model (tool-facing behavior)
- `docs/design/state/execution_log.md` — Tool result shape (native result model)

---

## Data Model

### Native ToolResult

```python
@dataclass
class ToolResult:
    """Structured result from any tool execution."""
    success: bool                    # True if tool completed without error
    output: str                      # Primary output (stdout, file content, etc.)
    error: str | None = None         # Error message if execution failed
    metadata: dict | None = None     # Extra info: exit_code, timed_out, chars_written, etc.
    duration: float = 0.0            # Execution duration in seconds
```

### Task Data Model

The `Task` and `TaskResult` entities are defined in `tinycua_sdk`. This design does not redefine them — it documents how the tools interact with them.

```python
# Task (defined in tinycua_sdk)
# Fields: task_id, task_name, task_description, task_context, success_criteria,
#         confidence, parent_task_id, child_tasks, task_result
# Key methods: at_id(task_id) -> Task | None  (DFS traversal)
#              traverse() -> Task | None       (DFS pre-order, next non-completed leaf)
#              display() -> str                (markdown tree with status markers)
#              root() -> Task                  (follow parent_task_id chain to root)

# TaskResult (defined in tinycua_sdk)
# Fields: status (TaskStatus), result (str), discovered_sequence_issues (list[str] | None),
#         uncertainty_notes (list[str] | None)
```

### TodoList Storage

```python
# Stored on Session:
session.todo_list: list[dict] | None = None
# Each item: {"status": "incomplete" | "completed", "todo": str}
```

---

## API / Interface Contracts

### Native Tool Signatures

```python
@tool
def run_shell(command: str, timeout: int = 30) -> dict:
    """Execute a shell command. Returns {stdout, stderr, exit_code, timed_out, error}."""

@tool
def read_file(path: str, start: int | None = None, offset: int | None = None) -> str | dict:
    """Read file contents. Full-file with truncation, or line-range read."""

@tool
def write_file(path: str, content: str) -> dict:
    """Write content to file, creating parent dirs if needed."""

@tool
def list_files(path: str, pattern: str = "*") -> list[str] | dict:
    """List files matching glob in directory."""

@tool
def fetch_url(url: str, method: str = "GET", headers: dict | None = None,
              timeout: int = 30, max_size: int = 102400) -> str | dict:
    """Fetch URL content. Large responses truncated."""

@tool
def run_python(code: str, timeout: int = 30) -> dict:
    """Execute Python code in subprocess. Returns {stdout, stderr, exit_code, timed_out, error}."""
```

### Task Tool Signatures

```python
@tool
def ReadActiveTask() -> dict | None:
    """Return the next active (non-completed) leaf task via DFS pre-order traversal."""

@tool
def ReadTask(task_id: str) -> dict | None:
    """Return a specific task by ID."""

@tool
def ListTask() -> str:
    """Return the task tree as formatted markdown with status markers."""

@tool
def TaskInit(primary_task_data: dict, sub_tasks: list[dict] | None = None) -> dict:
    """Replace entire task tree with new root + optional children."""

@tool
def SetSubTask(parent_task_id: str, sub_tasks: list[dict]) -> dict:
    """Replace parent's entire child_tasks list."""

@tool
def AddSubTask(parent_task_id: str, sub_tasks: list[dict]) -> dict:
    """Append new children to existing parent."""

@tool
def DeleteSubTask(task_id: str | list[str]) -> dict:
    """Delete task(s) and all descendants. Root cannot be deleted."""

@tool
def EditSubTask(task_id: str, task_data: dict) -> dict:
    """Edit metadata fields only (not structural fields)."""

@tool
def SwapTask(task_id_1: str, task_id_2: str) -> dict:
    """Swap two tasks. Prevents ancestor circularity."""

@tool
def UpdateTaskResult(task_id: str, result_data: dict) -> dict:
    """Update task_result of any task by ID. For TaskAnalyzer."""

@tool
def UpdateActiveTaskResult(result_data: dict) -> dict:
    """Update only the active leaf task's task_result. For TaskExecutor."""
```

### TodoList Tool Signature

```python
@tool
def TodoList(action: str, index: int | None = None, todo: str | None = None) -> str:
    """Per-session short-term goal tracking.
    
    Actions: add, read, mark_complete, mark_incomplete, edit, delete, clear.
    Returns formatted markdown checklist.
    """
```

### Digester Tool Signatures

```python
def create_enhanced_context_retrieval(
    cache_path: str,
    model: LanguageModel,
    exploration_tools: list[Tool] = EXPLORATION_TOOL,
) -> Tool:
    """Factory: creates a tool that spawns inner transient retrieval agents."""

@tool
def digest_information(
    context_summary: str,
    key_points: list[str],
    advisory_instructions: str | None = None,
    constraints: list[str] | None = None,
    known_gaps: list[str] | None = None,
) -> str:
    """Produce structured digest output. Prefixes output with DIGEST_INFO::."""
```

### Error Handling

| Error Case | Return / Exception |
|------------|-------------------|
| File not found | `{"error": "File not found: <path>"}` |
| Directory not found | `{"error": "Directory not found: <path>"}` |
| Command timeout | `{"stdout": "...", "stderr": "...", "exit_code": -1, "timed_out": true}` |
| Python execution error | `{"stdout": "", "stderr": "<traceback>", "exit_code": 1, "timed_out": false}` |
| HTTP error | `{"error": "HTTP <code>: <reason>"}` |
| Invalid task ID | `{"error": "Task not found: <task_id>"}` |
| Delete root task | `{"error": "Cannot delete root task"}` |
| Circular swap | `{"error": "Cannot swap ancestor with descendant"}` |
| Active task not found | `{"error": "No active task available."}` |
| Invalid TodoList index | Descriptive error string |

All tools catch unexpected exceptions internally and return error dicts — no unhandled exceptions propagate to the agent loop.

---

## Implementation Phases

### Phase 1 — Native Tools (already in progress via native_tools spec)

- [ ] Verify existing native tools are SDK-compatible (`@tool` decorated, JSON-serializable return)
- [ ] Create `tinycua/tools/result.py` with `ToolResult` dataclass
- [ ] Move/adapt tool implementations from `tinycua/agent/tools/native/` to `tinycua/tools/native/`
- [ ] Ensure all error paths return structured error dicts

### Phase 2 — Task Tools

- [ ] Create `tinycua/tools/task/` package
- [ ] Implement `_mutation.py` — `_apply_task_mutation`, `_reindex_tree`, `_remove_by_id`, `_collect_ids`
- [ ] Implement `read.py` — `ReadActiveTask`, `ReadTask`, `ListTask`
- [ ] Implement `write.py` — all 8 task mutation tools
- [ ] Write unit tests for each tool (happy + error + edge cases)
- [ ] Write integration tests for tree operations through SDK

### Phase 3 — TodoList Tool

- [ ] Implement `tinycua/tools/todo.py` — `TodoList` tool with sub-command dispatch
- [ ] Store on `session.todo_list`
- [ ] Write unit tests for all 7 sub-commands

### Phase 4 — Digester Retrieval Tool Interface

- [ ] Implement `tinycua/tools/digester.py` — `create_enhanced_context_retrieval` factory + `digest_information`
- [ ] Define `CONTEXT_CACHE_TOOLS` and `EXPLORATION_TOOL` constants

### Phase 5 — Tool Constants

- [ ] Create `tinycua/constants/tools.py`
- [ ] Define `SHARED_AGENT_BASE_TOOLS`, `READ_ONLY_TASK_TOOLS`, `WRITE_TASK_TOOLS`, and all `*_BASE_TOOLS`
- [ ] Define `CONTEXT_CACHE_TOOLS`, `EXPLORATION_TOOL`

### Phase 6 — Integration & Verification

- [ ] All tools importable and callable through SDK
- [ ] End-to-end test: native tools + task tools + todo tool in scenario
- [ ] `cd src/tinycua && uv run pytest tests/test_tools* tests/test_task_tools* tests/test_todo*` passes

---

## Technical Decisions

1. **Decision**: Separate `tinycua/tools/` package from `tinycua/agent/tools/`.
   - **Reason**: `tinycua/tools/` is the canonical tool implementation. `tinycua/agent/tools/` may contain agent-specific tool wrappers or adapters. Clean separation prevents circular imports and keeps the tool layer independent of agent internals.
   - **Alternatives Considered**: Keep everything in `tinycua/agent/tools/` — works but mixes concerns.

2. **Decision**: `ToolResult` as a simple `@dataclass` with `.to_dict()`, not a Pydantic model.
   - **Reason**: No validation needed at this level. Pydantic adds a dependency and overhead for what is fundamentally a plain data carrier. The SDK already handles JSON serialization.
   - **Alternatives Considered**: Pydantic BaseModel — overkill for a simple result container.

3. **Decision**: Task mutation tools follow the `_apply_task_mutation` pattern (clone → mutate → re-index → atomic swap).
   - **Reason**: Prevents partial mutations on failure. Re-indexing ensures task IDs always reflect current tree position.
   - **Alternatives Considered**: In-place mutation — simpler but loses safety guarantees on failure.

4. **Decision**: `TodoList` is a single tool with sub-command dispatch (`action` parameter), not separate tools per action.
   - **Reason**: Keeps tool count low. All list operations through one interface. Consistent with the design doc.
   - **Alternatives Considered**: Separate tools per action (AddTodo, ReadTodo, etc.) — more granular but increases tool count unnecessarily.

5. **Decision**: `enhanced_context_retrieval` is a factory function returning a `Tool`, not a standalone tool.
   - **Reason**: The inner agent needs `cache_path` and `model` configured at construction time. A factory captures these dependencies and produces a ready-to-use tool instance.
   - **Alternatives Considered**: Tool with all parameters at call time — too many parameters for the LLM to manage correctly.

6. **Decision**: `*_BASE_TOOLS` constants are module-level lists in `tinycua/constants/tools.py`, not computed per-call.
   - **Reason**: The tool sets are static per agent node type. Module-level constants are importable and testable without instantiation.
   - **Alternatives Considered**: Computed per AgentNode.run() — more flexible but harder to test and reason about.

7. **Decision**: Tools receive `session` via closure, not as a parameter.
   - **Reason**: Matches the SDK's tool registration pattern. The tool executor binds the session at construction time, keeping the tool interface clean for the LLM.
   - **Alternatives Considered**: Session as a tool parameter — visible to the LLM, which should not manage session state.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `run_shell` executes dangerous commands | Medium | High | Scope: benchmarks run in controlled environments. Future: sandboxing. |
| `run_python` infinite loops | Medium | Medium | Configurable timeout (default 30s) enforced by subprocess kill. |
| Task tree re-indexing bugs | Medium | High | Comprehensive unit tests for all mutation paths. Re-indexing logic tested independently. |
| Circular swap detection failure | Low | High | `_is_ancestor` check before swap. Unit tests verify ancestor detection. |
| SDK compatibility gaps | Medium | Medium | All tools tested through `ToolExecutor.execute()` in integration tests. |
| Session state management errors | Low | Medium | Tools receive session via closure; mutation tools use atomic swap pattern. |

---

## Open Questions _(optional)_

1. Should `ToolResult` be exposed as the return type of every tool, or is per-tool dict return sufficient?
   - **Current thinking**: Per-tool dict return for now (matching existing design docs). `ToolResult` is used by `ExecutionLog`, not as the tool's return type to the LLM.

2. Where exactly should the digester tools live — `tinycua/tools/digester.py` or in the agent nodes that use them?
   - **Current thinking**: `tinycua/tools/digester.py` — the tool interface is defined here, but the agent nodes (InformationDigester) consume it. This matches the pattern of `create_enhanced_context_retrieval` being a factory.

---

## References

- Spec: `./spec.md`
- Issue: [#70 — Prototype M1: Basic Tools](https://github.com/VJyzCELERY/TINYCUA/issues/70)
- Parent roadmap: [#60 — TINYCUA Minimal Prototype](https://github.com/VJyzCELERY/TINYCUA/issues/60)
- Design docs:
  - `docs/design/tools/task.md`
  - `docs/design/tools/todo.md`
  - `docs/design/tools/digester.md`
  - `docs/design/constants/tools.md`
  - `docs/design/state/task.md`
  - `docs/design/state/execution_log.md`
- Existing specs: `src/tinycua/specs/native_tools/spec.md` (scope: native execution tools only)
