# Design Document: M1 — Basic Tools

**Spec**: `./spec.md`
**Status**: Implemented
**Last Updated**: 2026-06-02

---

## Overview

M1 (Basic Tools) implements the foundational tool layer for the TINYCUA prototype. M1 delivers only **stateless tool primitives**: native execution tools (shell, file, web, python), the `ToolResult` model, and minimal tool constants. Orchestration-layer tools (TodoList, digester retrieval interface, per-agent tool constants) are deferred to M2. All tools are implemented as `tinycua_sdk` `@tool`-decorated functions. Together they form the executable surface that future agent nodes will use.

**Subprojects affected**: `tinycua`

---

## Architecture

### Component Overview

> **Path convention**: All paths below are relative to the `tinycua` Python package root (i.e., under `src/tinycua/tinycua/`). For example, `tinycua/tools/result.py` is located at `src/tinycua/tinycua/tools/result.py` on disk.

```
tinycua/
├── __init__.py                   # Package root
├── agent/
│   ├── __init__.py
│   └── tools/
│       ├── __init__.py           # Backward-compat re-exports from tinycua.tools
│       └── native/               # Backward-compat shim modules re-exporting from tinycua.tools.native
│           ├── __init__.py       # Re-exports from canonical tinycua.tools.native
│           ├── shell.py          # Shim → tinycua.tools.native.shell
│           ├── files.py          # Shim → tinycua.tools.native.files
│           ├── web.py            # Shim → tinycua.tools.native.web
│           └── python_exec.py    # Shim → tinycua.tools.native.python_exec
├── tools/                        # [NEW] — Canonical tool implementations
│   ├── __init__.py               # Public exports (all tool functions + ToolResult)
│   ├── result.py                 # Native ToolResult model
│   └── native/
│       ├── __init__.py           # Re-exports from individual modules
│       ├── shell.py              # run_shell (adapted from agent/tools/native/shell.py)
│       ├── files.py              # read_file, write_file, edit_file, list_files
│       ├── web.py                # fetch_url (adapted from agent/tools/native/web.py)
│       └── python_exec.py        # run_python (adapted from agent/tools/native/python_exec.py)
└── constants/                    # [NEW]
    └── tools.py                  # Tool constants (NATIVE_BASE_TOOLS, READ_ONLY_TASK_TOOLS ref)

# M2 additions (deferred): tinycua/tools/todo.py, tinycua/tools/digester.py,
# per-agent *BASE_TOOLS in tinycua/constants/tools.py
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/agent/tools/native/` | Backward-compat shims | Re-exports from `tinycua.tools.native.*` — do not add canonical implementations here |
| `tinycua/agent/tools/__init__.py` | Modified | Update exports to include all new tools |
| `tinycua/tools/` | New | New top-level package for tool implementations (separate from agent glue) |
| `tinycua/tools/result.py` | New | Native ToolResult dataclass |
| `tinycua/constants/tools.py` | New | NATIVE_BASE_TOOLS + READ_ONLY_TASK_TOOLS (forward ref) |
| `tinycua/tools/todo.py` | Deferred → M2 | TodoList tool with sub-command dispatch |
| `tinycua/tools/digester.py` | Deferred → M2 | create_enhanced_context_retrieval + digest_information |
| (per-agent *BASE_TOOLS) | Deferred → M2 | All agent-node-specific tool constants |

**Design docs addressed** (under `docs/design/`):
- `docs/design/state/execution_log.md` — Tool result shape (native result model)

> **Note — M2 Deferral**: The following design docs are **deferred to M2** because their tools depend on orchestration-layer state or state objects not yet available:
> - `docs/design/tools/todo.md` — TodoList tool specification (needs TodoList orchestration state)
> - `docs/design/tools/digester.md` — Digester tool interface (needs digester context cache)
> - `docs/design/constants/tools.md` — Per-agent `*_BASE_TOOLS` mappings (all reference orchestration-layer tools or agent nodes)
> - `docs/design/tools/task.md` — Task read/write tools (needs `Task`/`TaskResult` state objects)
> - `docs/design/state/task.md` — Task tree state model

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
    metadata: dict[str, Any] = field(default_factory=dict)  # Extra info: exit_code, timed_out, chars_written, etc.
    duration: float = 0.0            # Execution duration in seconds
```

> **Note — M2 Deferral**: The Task data model (task tree structure, node schema, traversal/mutation helpers), TaskResult model, TodoList storage, and digester cache state are all deferred to M2. See `src/tinycua/specs/basic-tools/spec.md` for details.

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
def edit_file(path: str, start: int, content: str,
              offset: int | None = None) -> dict:
    """Replace a range of lines in an existing file.
    Returns {success, path, start_line, lines_replaced, bytes_written, error}."""

@tool
def list_files(path: str = ".", pattern: str = "*") -> list[str] | dict:
    """List files matching glob in directory."""

@tool
def fetch_url(url: str, method: str = "GET", headers: dict | None = None,
              timeout: int = 30, max_size: int = 102400) -> str | dict:
    """Fetch URL content. Large responses truncated."""

@tool
def run_python(code: str, timeout: int = 30) -> dict:
    """Execute Python code in subprocess. Returns {stdout, stderr, exit_code, timed_out, error}."""
```

### Error Handling

| Error Case | Return / Exception |
|------------|-------------------|
| File not found | `{"error": "File not found: <path>"}` |
| Directory not found | `{"error": "Directory not found: <path>"}` |
| Command timeout | `{"stdout": "...", "stderr": "...", "exit_code": -1, "timed_out": true}` |
| Python execution error | `{"stdout": "", "stderr": "<traceback>", "exit_code": 1, "timed_out": false}` |
| HTTP error | `{"error": "HTTP <code>: <reason>"}` |

All tools catch unexpected exceptions internally and return error dicts — no unhandled exceptions propagate to the agent loop.

---

## Implementation Phases

### Phase 1 — ToolResult Model + Tool Constants

- [x] Create `tinycua/tools/result.py` with `ToolResult` dataclass
- [x] Create `tinycua/constants/tools.py` with `NATIVE_BASE_TOOLS` and `READ_ONLY_TASK_TOOLS` (forward ref)

### Phase 2 — Native Tools (already in progress via native_tools spec)

- [x] Verify existing native tools are SDK-compatible (`@tool` decorated, JSON-serializable return)
- [x] Move/adapt tool implementations from `tinycua/agent/tools/native/` to `tinycua/tools/native/`
- [x] Ensure all error paths return structured error dicts

### Phase 3 — Integration & Verification

- [x] All tools importable and callable through SDK
- [x] End-to-end test: native tools work together in scenario
- [x] `cd src/tinycua && uv run pytest` passes

### Phase 4 — Update Existing Package Exports

- [x] Update `tinycua/agent/tools/__init__.py` — add new tool imports for backward compat
- [x] Update `tinycua/tools/__init__.py` — ensure all tools are publicly exported

> **Note — M2 Deferral**: The following phases from the original plan are **deferred to M2**:
> - **Task Tools** (original Phase 2): All task read/write tools (`ReadActiveTask`, `ReadTask`, `ListTask`, `TaskInit`, `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, `UpdateTaskResult`, `UpdateActiveTaskResult`) and the `_mutation.py` internal helpers. See `src/tinycua/specs/basic-tools/spec.md` for details.
> - **TodoList Tool** (original Phase 3): Goal tracking on `todo_list`.
> - **Digester Tool Interface** (original Phase 4): `create_enhanced_context_retrieval` factory + `digest_information`.
> - **Per-Agent Tool Constants** (original Phase 5): `SHARED_AGENT_BASE_TOOLS`, `TASK_EXECUTOR_BASE_TOOLS`, `RESULT_REVIEWER_BASE_TOOLS`, `QUERY_ANALYST_BASE_TOOLS`, `INFORMATION_DIGESTER_BASE_TOOLS`, `TASK_ANALYZER_BASE_TOOLS`, `TASK_ASSESSOR_BASE_TOOLS`, `PRIMARY_AGENT_BASE_TOOLS`, `CONTEXT_CACHE_TOOLS`, `EXPLORATION_TOOL`.

---

## Technical Decisions

1. **Decision**: Separate `tinycua/tools/` package from `tinycua/agent/tools/`.
   - **Reason**: `tinycua/tools/` is the canonical tool implementation. `tinycua/agent/tools/` may contain agent-specific tool wrappers or adapters. Clean separation prevents circular imports and keeps the tool layer independent of agent internals.
   - **Alternatives Considered**: Keep everything in `tinycua/agent/tools/` — works but mixes concerns.

2. **Decision**: `ToolResult` as a simple `@dataclass` with `.to_dict()`, not a Pydantic model.
   - **Reason**: No validation needed at this level. Pydantic adds a dependency and overhead for what is fundamentally a plain data carrier. The SDK already handles JSON serialization.
   - **Alternatives Considered**: Pydantic BaseModel — overkill for a simple result container.

3. **Decision**: File tools resolve all paths against `TINYCUA_TOOL_ROOT` to prevent unintended filesystem access.
   - **Reason**: Security sandbox. The `_resolve_path` helper checks that resolved paths stay within the root, rejecting escapes (including via symlinks). When `TINYCUA_TOOL_ROOT` is unset, falls back to CWD.
   - **Alternatives Considered**: No sandbox — rejected due to benchmark safety requirements.

> **Note — M2 Deferred Decisions**: The following technical decisions are recorded here for completeness but are **deferred to M2** implementation:
> - **TodoList sub-command dispatch**: Single tool with `action` parameter vs. separate tools per action — design doc choice is single tool.
> - **create_enhanced_context_retrieval**: Factory function returning a `Tool` vs. standalone tool — design doc choice is factory.
> - **`*_BASE_TOOLS` constants**: Module-level lists vs. computed per-call — design doc choice is module-level constants.


---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `run_shell` executes dangerous commands | Medium | High | Scope: benchmarks run in controlled environments. Future: sandboxing. |
| `run_python` infinite loops | Medium | Medium | Configurable timeout (default 30s) enforced by subprocess kill. |
| SDK compatibility gaps | Medium | Medium | All tools tested through `AgentExecutor.execute()` in integration tests. |

---

## Open Questions _(optional)_

1. Should `ToolResult` be exposed as the return type of every tool, or is per-tool dict return sufficient?
   - **Current thinking**: Per-tool dict return for now (matching existing design docs). `ToolResult` is used by `ExecutionLog`, not as the tool's return type to the LLM.

2. Where should the digester tools live? *(M2 question — design doc choice is `tinycua/tools/digester.py`)*

3. Should the constants module in M1 include a `NATIVE_BASE_TOOLS` constant, or define only `READ_ONLY_TASK_TOOLS` as a forward ref?
   - **Current thinking**: Include `NATIVE_BASE_TOOLS` as a useful convenience for native tool registration. `READ_ONLY_TASK_TOOLS` is purely a forward reference placeholder.

---

## References

- Spec: `./spec.md`
- Issue: [#70 — Prototype M1: Basic Tools](https://github.com/VJyzCELERY/TINYCUA/issues/70)
- Parent roadmap: [#60 — TINYCUA Minimal Prototype](https://github.com/VJyzCELERY/TINYCUA/issues/60)
- Design docs:
  - `docs/design/state/execution_log.md` *(tool result shape only)*
  - `docs/design/tools/todo.md` *(deferred to M2)*
  - `docs/design/tools/digester.md` *(deferred to M2)*
  - `docs/design/constants/tools.md` *(deferred to M2)*
  - `docs/design/tools/task.md` *(deferred to M2)*
  - `docs/design/state/task.md` *(deferred to M2)*
- Existing specs: `src/tinycua/specs/native_tools/spec.md` (scope: native execution tools only)
