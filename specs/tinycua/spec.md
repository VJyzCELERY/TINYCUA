# Feature Specification: M1 — Basic Tools

**Status**: Draft
**Created**: 2026-06-02
**Last Updated**: 2026-06-02
**Subproject(s) Affected**: tinycua (core library)

---

## Problem Statement _(mandatory)_

- **Goals**: Implement the basic tool layer so that a future Task Executor can call sandboxed local tool actions and return structured observations. This is the executable surface that agents and benchmark automation will use later.
- **Gaps**: No structured tool result model exists. Shell, file, HTTP, Python, task, and todo tools are not yet implemented. The core library lacks the foundational layer needed by all higher-level agent and orchestration components.
- **Non-Goals**: Agent execution, custom loops, AgentNode classes, graph orchestration, CLI, WildClawBench batch runner. Durable persistence of tool results. Full browser/GUI automation (unless required by selected benchmark subset; if so, define only the minimal adapter contract).
- **Constraints**: Tool interfaces must be compatible with `tinycua-sdk` tool registration. Tool results must map to the future `ExecutionLog` model shape. File tools must enforce allowed-path security. Shell tools must support timeout and output capture.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A future Task Executor (or test harness) instantiates a tool (e.g., shell, file read), calls it with valid arguments, and receives a structured result object containing success/failure status, output, error details, metadata, and duration.

### Acceptance Scenarios

1. **Given** a shell tool, **When** invoked with `echo hello`, **Then** it returns a structured success result with `stdout: "hello"`.
2. **Given** a shell tool, **When** invoked with a command that times out, **Then** it returns a structured failure result with a timeout error.
3. **Given** a file read tool, **When** invoked with an allowed path, **Then** it returns the file contents in a success result.
4. **Given** a file read tool, **When** invoked with a disallowed path, **Then** it returns a structured failure result with a security violation error.
5. **Given** task mutation tools, **When** creating and modifying a task tree, **Then** the task tree structure is preserved and valid.
6. **Given** the TodoList tool, **When** adding, listing, updating, and clearing todos, **Then** each operation produces the expected state.

### Edge Cases

- What happens when shell command produces empty stdout but non-zero exit code?
- How does the system handle very large file reads (memory bounds)?
- What is the behavior with empty/null inputs to task tools?
- What happens when HTTP fetch times out or returns non-2xx status?
- How does the Python execution tool handle infinite loops or excessive resource usage?

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST define a native tool result model with success/failure status, output, error, metadata, and duration fields.
- **FR-002**: System MUST provide a shell execution tool with configurable timeout and captured stdout/stderr.
- **FR-003**: System MUST provide file read, file write, and file list/glob tools that enforce allowed-path security.
- **FR-004**: System MUST provide an HTTP fetch tool (if required by the selected benchmark subset).
- **FR-005**: System MUST provide a Python/code execution tool (if required by the selected benchmark subset).
- **FR-006**: System MUST provide task read tools: `ReadActiveTask`, `ReadTask`, `ListTask`.
- **FR-007**: System MUST provide task mutation tools: `TaskInit`, `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, `UpdateTaskResult`, `UpdateActiveTaskResult`.
- **FR-008**: System MUST provide a `TodoList` tool with add/list/update/clear operations.
- **FR-009**: All tools MUST be wrappable for `tinycua-sdk` tool registration.
- **FR-010**: Tool results MUST be shaped to be usable by a future `ExecutionLog`.

### Key Entities

- **ToolResult**: Structured result object — success/failure flag, output string, error string, metadata dict, duration float.
- **ToolBase**: Abstract base class or protocol that all tools implement — provides a common `execute` or `__call__` interface.
- **ShellTool**: Executes shell commands with timeout, captures stdout/stderr, returns ToolResult.
- **FileTool**: Reads/writes/lists files with path allowlist enforcement.
- **TaskTool**: Reads and mutates task tree state (TaskInit, SetSubTask, etc.).
- **TodoListTool**: Manages a todo list with add/list/update/clear.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

Objective, measurable checks that prove the problem is solved.

- [ ] **Tool result model**: Native ToolResult with success/failure, output, error, metadata, duration exists and is tested.
- [ ] **Shell tool**: Executes commands, captures output, handles timeout.
- [ ] **File tools**: Read, write, and glob/list operations work with path security.
- [ ] **HTTP fetch tool**: GET requests return structured results (if in scope).
- [ ] **Python execution tool**: Runs Python code snippets and returns output (if in scope).
- [ ] **Task tools**: All read and mutation tools create and preserve valid task tree structures.
- [ ] **Todo tool**: add/list/update/clear operations behave correctly.
- [ ] **SDK compatibility**: All tools can be registered via `tinycua-sdk` tool registration.
- [ ] **ExecutionLog compatibility**: Tool results match the shape expected by `ExecutionLog`.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Each native tool returns structured success result.
- Each native tool returns structured failure result.
- Shell timeout is handled and returns failure result.
- File tools enforce allowed paths (success within allowlist, failure outside).
- Task tools preserve valid task tree structure across mutations.
- Todo tool add/list/update/clear behavior.

### Integration Tests

- Tools work together: shell output piped as file content, file read followed by task creation.
- Tool results are correctly parseable by a future result consumer.

### Manual Tests _(if applicable)_

- N/A — all tool behavior is verifiable via unit/integration tests.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| ToolResult model | TODO | Foundation for all tools |
| Shell tool | TODO | |
| File tools | TODO | Read, write, list/glob |
| HTTP fetch tool | TODO | If required |
| Python exec tool | TODO | If required |
| Task tools | TODO | Read + mutation |
| Todo tool | TODO | |
| SDK wrappers | TODO | |

---

## Open Questions _(optional)_

1. **Which subproject owns the core tool implementations?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-05
   - **Status**: Discussion
   - **Proposed Answer**: `tinycua` core library — tools live in `src/tinycua/tools/` with tests in `src/tinycua/tests/`.

2. **Should HTTP fetch and Python exec be in M1 scope?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-05
   - **Status**: Discussion
   - **Proposed Answer**: Include if the selected benchmark subset requires them; otherwise defer to later milestone.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
