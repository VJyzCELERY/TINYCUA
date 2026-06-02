# Design Document: M1 — Basic Tools

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-02

---

## Overview

M1 (Basic Tools) implements the foundational tool layer for the TINYCUA prototype. This includes native execution tools (shell, file, web, python), a TodoList tool, a digester retrieval tool interface, and the tool constants/mappings that wire them into agent nodes. All tools are implemented as `tinycua_sdk` `@tool`-decorated functions. Together they form the executable surface that every agent node will use.

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
│   ├── todo.py                  # TodoList tool
│   └── digester.py              # create_enhanced_context_retrieval, digest_information
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
| `tinycua/tools/todo.py` | New | TodoList tool with sub-command dispatch |
| `tinycua/tools/digester.py` | New | create_enhanced_context_retrieval + digest_information |
| `tinycua/constants/tools.py` | New | *_BASE_TOOLS constant definitions |

**Design docs addressed** (under `docs/design/`):
- `docs/design/tools/todo.md` — TodoList tool specification
- `docs/design/tools/digester.md` — Digester tool interface
- `docs/design/constants/tools.md` — Tool constant mappings
- `docs/design/state/execution_log.md` — Tool result shape (native result model)

> **Note — M2 Deferral**: Task tool design docs (`docs/design/tools/task.md`, `docs/design/state/task.md`) are deferred to M2 pending `Task`/`TaskResult` state object implementation in the SDK.

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

> **Note — M2 Deferral**: The Task data model (task tree structure, node schema, traversal/mutation helpers) and TaskResult model are deferred to M2. See `src/tinycua/specs/basic-tools/spec.md` for details.

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
| Invalid TodoList index | Descriptive error string |

All tools catch unexpected exceptions internally and return error dicts — no unhandled exceptions propagate to the agent loop.

---

## Implementation Phases

### Phase 1 — Native Tools (already in progress via native_tools spec)

- [ ] Verify existing native tools are SDK-compatible (`@tool` decorated, JSON-serializable return)
- [ ] Create `tinycua/tools/result.py` with `ToolResult` dataclass
- [ ] Move/adapt tool implementations from `tinycua/agent/tools/native/` to `tinycua/tools/native/`
- [ ] Ensure all error paths return structured error dicts

> **Note — M2 Deferral**: Task Tools (Phase 2 in the original plan) are deferred to M2. This includes all task read/write tools (`ReadActiveTask`, `ReadTask`, `ListTask`, `TaskInit`, `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, `UpdateTaskResult`, `UpdateActiveTaskResult`) and the `_mutation.py` internal helpers. See `src/tinycua/specs/basic-tools/spec.md` for details.

### Phase 2 — TodoList Tool

- [ ] Implement `tinycua/tools/todo.py` — `TodoList` tool with sub-command dispatch
- [ ] Store on `session.todo_list`
- [ ] Write unit tests for all 7 sub-commands

### Phase 3 — Digester Retrieval Tool Interface

- [ ] Implement `tinycua/tools/digester.py` — `create_enhanced_context_retrieval` factory + `digest_information`

### Phase 4 — Tool Constants

- [ ] Create `tinycua/constants/tools.py`
- [ ] Define `SHARED_AGENT_BASE_TOOLS` and all `*_BASE_TOOLS` for each agent node type
- [ ] Define `CONTEXT_CACHE_TOOLS`, `EXPLORATION_TOOL`

### Phase 5 — Integration & Verification

- [ ] All tools importable and callable through SDK
- [ ] Update `tinycua/agent/tools/__init__.py` — add new tool imports for backward compat
- [ ] Update `tinycua/tools/__init__.py` — ensure all tools are publicly exported
- [ ] End-to-end test: native tools + todo tool in scenario
- [ ] `cd src/tinycua && uv run pytest tests/test_tools* tests/test_todo*` passes

---

## Technical Decisions

1. **Decision**: Separate `tinycua/tools/` package from `tinycua/agent/tools/`.
   - **Reason**: `tinycua/tools/` is the canonical tool implementation. `tinycua/agent/tools/` may contain agent-specific tool wrappers or adapters. Clean separation prevents circular imports and keeps the tool layer independent of agent internals.
   - **Alternatives Considered**: Keep everything in `tinycua/agent/tools/` — works but mixes concerns.

2. **Decision**: `ToolResult` as a simple `@dataclass` with `.to_dict()`, not a Pydantic model.
   - **Reason**: No validation needed at this level. Pydantic adds a dependency and overhead for what is fundamentally a plain data carrier. The SDK already handles JSON serialization.
   - **Alternatives Considered**: Pydantic BaseModel — overkill for a simple result container.

3. **Decision**: `TodoList` is a single tool with sub-command dispatch (`action` parameter), not separate tools per action.
   - **Reason**: Keeps tool count low. All list operations through one interface. Consistent with the design doc.
   - **Alternatives Considered**: Separate tools per action (AddTodo, ReadTodo, etc.) — more granular but increases tool count unnecessarily.

4. **Decision**: `create_enhanced_context_retrieval` is a factory function returning a `Tool`, not a standalone tool.
   - **Reason**: The inner agent needs `cache_path` and `model` configured at construction time. A factory captures these dependencies and produces a ready-to-use tool instance.
   - **Alternatives Considered**: Tool with all parameters at call time — too many parameters for the LLM to manage correctly.

5. **Decision**: `*_BASE_TOOLS` constants are module-level lists in `tinycua/constants/tools.py`, not computed per-call.
   - **Reason**: The tool sets are static per agent node type. Module-level constants are importable and testable without instantiation.
   - **Alternatives Considered**: Computed per AgentNode.run() — more flexible but harder to test and reason about.

6. **Decision**: Tools access `session` via a module-level `_session` variable, initialized by a factory or setter before tool registration.
   - **Reason**: Keeps tool signatures clean for the LLM (no session parameter) while remaining mockable in tests via `unittest.mock.patch`. The factory/initializer pattern (`set_session(session)` / `create_tools(session)`) allows per-session isolation without exposing session to the LLM.
   - **Alternatives Considered**: Closure-based injection — cleaner conceptually but harder to test without a factory registry. Session as a tool parameter — visible to the LLM, which should not manage session state.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `run_shell` executes dangerous commands | Medium | High | Scope: benchmarks run in controlled environments. Future: sandboxing. |
| `run_python` infinite loops | Medium | Medium | Configurable timeout (default 30s) enforced by subprocess kill. |
| SDK compatibility gaps | Medium | Medium | All tools tested through `AgentExecutor.execute()` in integration tests. |
| Session state management errors | Low | Medium | Tools receive session via closure. |

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
  - `docs/design/tools/todo.md`
  - `docs/design/tools/digester.md`
  - `docs/design/constants/tools.md`
  - `docs/design/state/execution_log.md`
  - `docs/design/tools/task.md` *(deferred to M2)*
  - `docs/design/state/task.md` *(deferred to M2)*
- Existing specs: `src/tinycua/specs/native_tools/spec.md` (scope: native execution tools only)
