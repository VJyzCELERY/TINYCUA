# Feature Specification: Prototype M1 — Basic Tools

**Status**: Draft
**Created**: 2026-06-02
**Last Updated**: 2026-06-02
**Subproject(s) Affected**: tinycua, tinycua-sdk

---

## Problem Statement

- **Goals**: Implement the basic tool layer — the executable surface that the Task Executor and benchmark automation will use. After M1, the prototype can execute sandboxed local tool actions and return structured observations. No agents or graph orchestration are required yet.
- **Gaps**: The `src/tinycua/tinycua/agent/tools/` directory exists but contains only skeletons. State objects (Session, Task tree, etc.) have been implemented as typed Python classes, but no tools to read or mutate task state exist. There is no tool to manage the executor-local todo list. No tool wrappers compatible with `tinycua-sdk` tool registration exist yet.
- **Non-Goals**: Agent orchestration, graph-based workflows, the Information Digester, Query Analyst, or Result Reviewer agents. Internal agent-calling tools. Tool permission workflows beyond the SDK's built-in allow/ask/deny. Enhanced Context Retrieval. These are separate milestones (M2+).
- **Constraints**: All tools must be decorated with `tinycua_sdk`'s `@tool` decorator. All tools must return JSON-serializable results. All tools must handle errors gracefully (return structured error dicts, not exceptions). Shell and code execution must have configurable timeouts. File tools must work within the allowed project boundary. Task tools must preserve valid task tree structure.

---

## User Scenarios & Testing

### Primary Scenario

A developer wants to run the prototype against a benchmark task. They register all basic tools with an SDK Agent, then invoke them through `ToolExecutor`. The agent can:
- Execute shell commands and capture stdout/stderr/exit code
- Read, write, list, and edit files within the allowed boundary
- Fetch URLs via HTTP (if enabled)
- Run Python code snippets (if enabled)
- Read the active task, specific task by ID, or list all tasks
- Create and mutate the task tree (init, add/edit/delete subtasks, swap, update results)
- Manage an executor-local todo list (add, list, update, clear items)

### Acceptance Scenarios

1. **Given** the basic tools layer is installed, **When** an agent calls `run_shell` with a valid command, **Then** stdout, stderr, and exit code are returned in a structured dict.
2. **Given** the basic tools layer, **When** an agent calls `read_file` with a valid path, **Then** file contents are returned as a string.
3. **Given** the basic tools layer, **When** an agent calls `write_file` with a path and content, **Then** the file is created/overwritten and a success confirmation is returned.
4. **Given** the basic tools layer, **When** an agent calls `list_files` with a directory and glob pattern, **Then** matching file paths are returned as a list.
5. **Given** the basic tools layer, **When** an agent calls `ReadActiveTask`, **Then** the current active task data is returned.
6. **Given** the basic tools layer, **When** an agent calls `TaskInit` with task parameters, **Then** a new task tree is created and the task is set as active.
7. **Given** the basic tools layer, **When** an agent calls `AddSubTask` on an existing task, **Then** a child task is added to the tree.
8. **Given** the basic tools layer, **When** an agent calls `TodoList` to add an item, **Then** the item appears in the subsequent `list` output.

### Edge Cases

- What happens when `run_shell` command times out?
- What happens when `read_file` path does not exist?
- What happens when `write_file` parent directory does not exist?
- What happens when `fetch_url` receives a non-200 response?
- What happens when `run_python` code has a syntax error or infinite loop?
- What happens when `TaskInit` is called while a task is already active?
- What happens when `DeleteSubTask` removes a task with children?
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

**Task Tools (Read/Mutate Task State)**

- **FR-010**: System MUST provide a `ReadActiveTask` tool that returns the currently active task's data from Session state.
- **FR-011**: System MUST provide a `ReadTask` tool that returns a specific task by ID from the Session task tree.
- **FR-012**: System MUST provide a `ListTask` tool that returns a flattened list of all tasks in the Session task tree with status markers.
- **FR-013**: System MUST provide a `TaskInit` tool that creates a new task tree in the Session, setting it as active.
- **FR-014**: System MUST provide a `SetSubTask` tool that replaces the subtask list of a given task.
- **FR-015**: System MUST provide an `AddSubTask` tool that appends a child task to a given parent task.
- **FR-016**: System MUST provide a `DeleteSubTask` tool that removes a child task by ID from a parent task.
- **FR-017**: System MUST provide an `EditSubTask` tool that updates a task's fields (name, description, context, success criteria).
- **FR-018**: System MUST provide a `SwapTask` tool that reorders two tasks in a parent's child list.
- **FR-019**: System MUST provide an `UpdateTaskResult` tool that sets the result (status, output) on a specific task.
- **FR-020**: System MUST provide an `UpdateActiveTaskResult` tool that sets the result on the currently active task.
- **FR-021**: All task tools MUST operate on the Session state held in a shared executor context.
- **FR-022**: Task tools MUST preserve valid task tree structure (no orphaned children, no duplicate IDs).

**Todo List Tool**

- **FR-023**: System MUST provide a `TodoList` tool that supports `add`, `list`, `update`, and `clear` operations on an executor-local todo list.
- **FR-024**: The todo list MUST be scoped to the executor session and not persist across restarts.

**SDK Integration**

- **FR-025**: All tools MUST be compatible with `tinycua_sdk`'s `@tool` decorator for schema generation and registration.
- **FR-026**: All tools MUST be invocable through the SDK's `ToolExecutor.execute()` method.
- **FR-027**: A public `register_all()` function or tools list MUST be exported so consumers can register all basic tools at once.

### Key Entities

- **Native Tool Result**: Structured dict returned by execution tools (`run_shell`, `write_file`, `run_python`) containing success/error fields. Data tools (`read_file`, `fetch_url`, `list_files`) return raw data (string or list) on success, dict on error.
- **Task Tool**: A `@tool`-decorated function that reads or mutates the Session's task tree through a shared executor context. Task tools accept and return JSON-serializable values.
- **TodoList**: An in-memory todo list attached to the executor session. Items are simple strings with an ID and status (pending/completed).
- **Executor Context**: A shared context object passed to tool functions that holds references to Session state, todo list, and configuration (allowed paths, timeouts, feature flags).

---

## Success Criteria

- [ ] **All native tools callable**: `run_shell`, `read_file`, `write_file`, `edit_file`, `list_files`, `fetch_url`, `run_python` — importable and return correct results.
- [ ] **All task tools callable**: `ReadActiveTask`, `ReadTask`, `ListTask`, `TaskInit`, `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, `UpdateTaskResult`, `UpdateActiveTaskResult` — create, read, mutate, and delete task tree nodes correctly.
- [ ] **TodoList fully functional**: `add`, `list`, `update`, `clear` all work as expected.
- [ ] **Tools work through SDK**: All tools can be registered with an SDK `Agent` and invoked through `ToolExecutor`.
- [ ] **Structured error handling**: File not found, timeout, invalid task ID — all return structured error results, not exceptions.
- [ ] **Timeouts enforced**: Shell and Python execution respect the configured timeout.
- [ ] **Task tree integrity**: No orphaned children after deletion, no duplicate task IDs.
- [ ] **Test suite passes**: `cd src/tinycua && uv run pytest tests/test_tools* tests/test_task_tools* tests/test_todo*`

---

## Testing Plan

### Unit Tests

- Each native tool tested in isolation with mocked/fake dependencies (temp directories for file tools, mock HTTP for fetch).
- Each task tool tested against a known Session with a task tree fixture.
- TodoList tested for add/list/update/clear behavior.
- Happy path: valid inputs produce expected outputs.
- Error paths: timeout, not found, invalid ID — return error results.
- Edge cases: empty file, empty command, empty task tree, duplicate IDs.

### Integration Tests

- Register all tools with a real SDK `Agent` and verify schema generation.
- Verify tool execution through `ToolExecutor.execute()`.
- Test multi-step workflow: init task → add subtask → set active → read task → update result → verify.

### Manual Tests

- None required — tools are deterministic and fully testable in code.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Native tools (shell, file, http, python) | In Progress | Spec'd in `native_tools/spec.md` |
| Task tools (read/mutate) | Draft | New — to be implemented in this milestone |
| TodoList tool | Draft | New — to be implemented in this milestone |
| SDK tool wrappers/registration | Draft | New — to be implemented in this milestone |
| Tests | Draft | To be written alongside implementation |

---

## Open Questions

1. **Should task tools use a global Session singleton or receive Session via context injection?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-03
   - **Status**: Discussion
   - **Proposed Answer**: Context injection via a shared `ExecutorContext` passed to tool factories. Avoids global state and makes testing easier.

2. **Should `fetch_url` and `run_python` be optional (behind feature flags)?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-03
   - **Status**: Discussion
   - **Proposed Answer**: Yes — these should be feature-gated since some benchmarks may not require them and they add security surface.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
