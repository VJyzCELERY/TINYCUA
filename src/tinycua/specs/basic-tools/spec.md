# Feature Specification: Prototype M1 — Basic Tools

**Status**: Under Review
**Created**: 2026-06-02
**Last Updated**: 2026-06-02
**Subproject(s) Affected**: tinycua, tinycua-sdk

---

## Problem Statement

- **Goals**: Implement the basic tool layer — the executable surface that the Task Executor and benchmark automation will use. After M1, the prototype can execute sandboxed local tool actions and return structured observations. No agents or graph orchestration are required yet.
- **Gaps**: The `src/tinycua/tinycua/agent/tools/` directory exists but contains only skeletons. There is no tool to manage the executor-local todo list. No tool wrappers compatible with `tinycua-sdk` tool registration exist yet. Task state objects (Session, Task tree, TaskResult) do not exist yet — they belong to M2 (Data Structures, Entity Relationships, and Rules, issue #71) and are out of scope for M1.
- **Non-Goals**: Agent orchestration, graph-based workflows, the Information Digester, Query Analyst, or Result Reviewer agents. Internal agent-calling tools. Task state management tools (ReadActiveTask, TaskInit, AddSubTask, etc.) — these depend on state objects from M2. Tool permission workflows beyond the SDK's built-in allow/ask/deny. Enhanced Context Retrieval. These are separate milestones (M2+).
- **Constraints**: All tools must be decorated with `tinycua_sdk`'s `@tool` decorator. All tools must return JSON-serializable results. All tools must handle errors gracefully (return structured error dicts, not exceptions). Shell and code execution must have configurable timeouts. File tools must work within the allowed project boundary.

---

## User Scenarios & Testing

### Primary Scenario

A developer wants to run the prototype against a benchmark task. They register all basic tools with an SDK Agent, then invoke them through `ToolExecutor`. The agent can:
- Execute shell commands and capture stdout/stderr/exit code
- Read, write, list, and edit files within the allowed boundary
- Fetch URLs via HTTP (if enabled)
- Run Python code snippets (if enabled)
- Manage an executor-local todo list (add, list, update, clear items)

### Acceptance Scenarios

1. **Given** the basic tools layer is installed, **When** an agent calls `run_shell` with a valid command, **Then** stdout, stderr, and exit code are returned in a structured dict.
2. **Given** the basic tools layer, **When** an agent calls `read_file` with a valid path, **Then** file contents are returned as a string.
3. **Given** the basic tools layer, **When** an agent calls `write_file` with a path and content, **Then** the file is created/overwritten and a success confirmation is returned.
4. **Given** the basic tools layer, **When** an agent calls `list_files` with a directory and glob pattern, **Then** matching file paths are returned as a list.
5. **Given** the basic tools layer, **When** an agent calls `TodoList` to add an item, **Then** the item appears in the subsequent `list` output.

### Edge Cases

- What happens when `run_shell` command times out?
- What happens when `read_file` path does not exist?
- What happens when `write_file` parent directory does not exist?
- What happens when `fetch_url` receives a non-200 response?
- What happens when `run_python` code has a syntax error or infinite loop?
- What happens when `TodoList.add` gets a duplicate item?
- How are large outputs handled (file too large, URL response too large)?

---

## Requirements

### Functional Requirements

**Native Tools (Shell, File, HTTP, Python)**

- **FR-001**: System MUST provide a `run_shell` tool that executes a shell command with configurable timeout, returning `{stdout, stderr, exit_code, timed_out}`.
- **FR-002**: System MUST provide a `read_file` tool that reads a file at a given path and returns its contents. Large files must be truncated with a clear indicator.
- **FR-003**: System MUST provide a `write_file` tool that creates or overwrites a file at a given path, creating parent directories if needed. Returns `{success, path, chars_written}`.
- **FR-004**: System MUST provide an `edit_file` tool that replaces lines in an existing file starting at a given line number with optional offset. Returns `{success, path, start_line, lines_replaced, bytes_written}`.
- **FR-005**: System MUST provide a `list_files` tool that lists files matching a glob pattern in a directory.
- **FR-006**: System MUST provide a `fetch_url` tool that performs HTTP requests (configurable method, headers, timeout) and returns the response body.
- **FR-007**: System MUST provide a `run_python` tool that executes Python code in an isolated subprocess with configurable timeout, returning `{stdout, stderr, exit_code, timed_out}`.
- **FR-008**: All native tools MUST return JSON-serializable results with structured error handling (error dicts, not exceptions).
- **FR-009**: Shell and Python execution MUST be bounded by configurable timeouts.

**Todo List Tool**

- **FR-010**: System MUST provide a `TodoList` tool that supports `add`, `list`, `update`, and `clear` operations on an executor-local todo list.
- **FR-011**: The todo list MUST be scoped to the executor session and not persist across restarts.

**SDK Integration**

- **FR-012**: All tools MUST be compatible with `tinycua_sdk`'s `@tool` decorator for schema generation and registration.
- **FR-013**: All tools MUST be invocable through the SDK's `ToolExecutor.execute()` method.
- **FR-014**: A public `register_all()` function or tools list MUST be exported so consumers can register all basic tools at once.

### Key Entities

- **Native Tool Result**: Structured dict returned by execution tools (`run_shell`, `write_file`, `run_python`) containing success/error fields. Data tools (`read_file`, `fetch_url`, `list_files`) return raw data (string or list) on success, dict on error.
- **TodoList**: An in-memory todo list attached to the executor session. Items are simple strings with an ID and status (pending/completed).
- **Executor Context**: A shared context object passed to tool functions that holds references to todo list, configuration (allowed paths, timeouts, feature flags), and a reserved slot for Session state when available in M2.

---

## Success Criteria

- [ ] **All native tools callable**: `run_shell`, `read_file`, `write_file`, `edit_file`, `list_files`, `fetch_url`, `run_python` — importable and return correct results.
- [ ] **TodoList fully functional**: `add`, `list`, `update`, `clear` all work as expected.
- [ ] **Tools work through SDK**: All tools can be registered with an SDK `Agent` and invoked through `ToolExecutor`.
- [ ] **Structured error handling**: File not found, timeout, invalid path — all return structured error results, not exceptions.
- [ ] **Timeouts enforced**: Shell and Python execution respect the configured timeout.
- [ ] **Test suite passes**: `cd src/tinycua && uv run pytest tests/test_tools* tests/test_todo*`

---

## Testing Plan

### Unit Tests

- Each native tool tested in isolation with mocked/fake dependencies (temp directories for file tools, mock HTTP for fetch).
- TodoList tested for add/list/update/clear behavior.
- Happy path: valid inputs produce expected outputs.
- Error paths: timeout, not found — return error results.
- Edge cases: empty file, empty command, duplicate IDs.

### Integration Tests

- Register all tools with a real SDK `Agent` and verify schema generation.
- Verify tool execution through `ToolExecutor.execute()`.

### Manual Tests

- None required — tools are deterministic and fully testable in code.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Native tools (shell, file, http, python) | In Progress | Spec'd in `native_tools/spec.md` |
| Task tools (read/mutate) | Deferred to M2 (#71) | Requires state objects (Session, Task, TaskResult) from M2 |
| TodoList tool | Implemented | `tinycua/agent/tools/todo/todo_list.py` |
| SDK tool wrappers/registration | Implemented | `register_all()` in `tools/__init__.py` |
| Tests | Implemented | 124 tests — 3 integration, 4 unit test classes |

---

## Open Questions

1. **Should task tools use a global Session singleton or receive Session via context injection?** (Deferred to M2 — requires state objects first)
   - **Owner**: @VJyzCELERY
   - **Target**: TBD (M2 planning)
   - **Status**: Decided
   - **Proposed Answer**: Context injection via a shared `ExecutorContext` passed to tool factories. Avoids global state and makes testing easier. See design.md Technical Decision #1 (line 245).

2. **Should `fetch_url` and `run_python` be optional (behind feature flags)?**
   - **Owner**: @VJyzCELERY
   - **Target**: Resolved
   - **Status**: Decided
   - **Proposed Answer**: Yes — feature-gated via `ExecutorConfig.enable_fetch` and `ExecutorConfig.enable_python_exec` (see design.md Technical Decision #3, line 253).

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
