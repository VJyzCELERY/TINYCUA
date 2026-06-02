# Feature Specification: M1 — Basic Tools

**Status**: Draft
**Created**: 2026-06-02
**Last Updated**: 2026-06-02
**Subproject(s) Affected**: tinycua-sdk, tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Provide the basic tool layer so that a future Task Executor can call sandboxed local tool actions and return structured observations, without needing to know CLI or graph internals.
- **Gaps**: No native tool result model exists. Shell, file, task, todo, and digester tools are unimplemented. Tool constants and mappings are not defined. There is no way to create, inspect, mutate, or mark task results programmatically.
- **Non-Goals**:
  - Agent execution, custom loops, AgentNode classes, graph orchestration, CLI, and WildClawBench batch runner.
  - Durable persistence of tool results.
  - Full browser/GUI automation (unless required for the selected benchmark subset; if required, only define the minimal adapter contract).
- **Constraints**:
  - Tool wrappers must be compatible with `tinycua-sdk` tool registration.
  - Tool result model must be usable by a future `ExecutionLog`.
  - Must reference existing design docs in `src/tinycua/docs/design/tools/` and `src/tinycua/docs/design/constants/`.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer writes a unit test that calls a shell tool with a command and timeout. The tool executes the command in a sandboxed environment, captures stdout/stderr, and returns a structured `ToolResult` with success/failure status, output, error, metadata, and duration.

### Acceptance Scenarios

1. **Given** a valid shell command, **When** the shell tool is invoked with a timeout, **Then** it returns a structured success result with captured stdout.
2. **Given** an invalid shell command, **When** the shell tool is invoked, **Then** it returns a structured failure result with the error message.
3. **Given** a shell command that exceeds the timeout, **When** the shell tool is invoked, **Then** it terminates the process and returns a timeout error result.
4. **Given** a file read request with an allowed path, **When** the file read tool is invoked, **Then** it returns the file contents.
5. **Given** a file read request with a disallowed path, **When** the file read tool is invoked, **Then** it returns a failure result due to path restriction.
6. **Given** task mutation operations, **When** tools like `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask` are invoked, **Then** they preserve valid task tree structure.
7. **Given** a todo list, **When** add/list/update/clear tools are invoked, **Then** they behave correctly.

### Edge Cases

- What happens when shell command is empty or null?
- How does the system handle extremely long command output?
- What is the behavior when file path traversal is attempted?
- What happens when task tree operations would create cycles or orphans?
- How does the system handle concurrent tool invocations?

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a native tool result model with success/failure status, output, error, metadata, and duration.
- **FR-002**: System MUST provide a shell execution tool with configurable timeout and captured stdout/stderr.
- **FR-003**: System MUST provide a file read tool that enforces allowed paths.
- **FR-004**: System MUST provide a file write tool that enforces allowed paths.
- **FR-005**: System MUST provide a file list/glob tool that enforces allowed paths.
- **FR-006**: System MUST provide an HTTP fetch tool if required by the selected benchmark subset.
- **FR-007**: System MUST provide a Python/code execution tool if required by the selected benchmark subset.
- **FR-008**: System MUST provide task read tools: `ReadActiveTask`, `ReadTask`, `ListTask`.
- **FR-009**: System MUST provide task mutation tools: `TaskInit`, `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, `UpdateTaskResult`, `UpdateActiveTaskResult`.
- **FR-010**: System MUST provide a `TodoList` tool with add/list/update/clear behavior.
- **FR-011**: System MUST provide tool wrappers compatible with `tinycua-sdk` tool registration.
- **FR-012**: System MUST provide tool constants/mappings from `design/constants/tools.md`.

### Key Entities

- **ToolResult**: Structured result with success/failure status, output, error, metadata, and duration.
- **ShellTool**: Executes shell commands with timeout and captured outputs.
- **FileReadTool**: Reads file contents with path restriction enforcement.
- **FileWriteTool**: Writes file contents with path restriction enforcement.
- **FileListTool**: Lists/glob files with path restriction enforcement.
- **HttpFetchTool**: Fetches URLs (if required).
- **CodeExecTool**: Executes code snippets (if required).
- **TaskTools**: Group of tools for task read/mutation operations.
- **TodoListTool**: Manages a todo list with add/list/update/clear.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

Objective, measurable checks that prove the problem is solved.

- [ ] **Tool tests pass**: `cd src/tinycua && uv run pytest tests/test_tools* tests/test_task_tools* tests/test_todo*`
- [ ] **Each native tool returns structured success result**: unit tested.
- [ ] **Each native tool returns structured failure result**: unit tested.
- [ ] **Shell timeout is handled**: unit tested.
- [ ] **File tools enforce allowed paths**: unit tested.
- [ ] **Task tools preserve valid task tree structure**: unit tested.
- [ ] **Todo tool add/list/update/clear behavior**: unit tested.
- [ ] **A future Task Executor can call the tool layer without knowing CLI or graph internals.**

---

## Testing Plan _(mandatory)_

### Unit Tests

- Unit test: each native tool returns structured success result.
- Unit test: each native tool returns structured failure result.
- Unit test: shell timeout is handled.
- Unit test: file tools enforce allowed paths.
- Unit test: task tools preserve valid task tree structure.
- Unit test: todo tool add/list/update/clear behavior.

### Integration Tests

- Integration test: end-to-end tool call flow through `tinycua-sdk` tool registration.
- Integration test: tool result model serialization/deserialization.

### Manual Tests _(if applicable)_

- N/A — all tests are automated.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Tool result model | TODO | |
| Shell execution tool | TODO | |
| File read/write/list tools | TODO | |
| HTTP fetch tool | TODO | Conditional on benchmark subset |
| Code execution tool | TODO | Conditional on benchmark subset |
| Task read tools | TODO | |
| Task mutation tools | TODO | |
| TodoList tool | TODO | |
| Tool constants/mappings | TODO | |

---

## Open Questions _(optional)_

1. **Which benchmark subset is selected for M1?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-05
   - **Status**: Discussion
   - **Proposed Answer**: TBD — determines whether HTTP fetch and code execution tools are required.

2. **What is the exact sandboxing mechanism for shell/code execution?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-05
   - **Status**: Discussion
   - **Proposed Answer**: Use subprocess with timeout and path restriction; full sandboxing may come later.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
