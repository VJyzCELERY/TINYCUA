# Feature Specification: M1 — Basic Tools

**Status**: Draft
**Created**: 2026-06-02
**Last Updated**: 2026-06-02
**Subproject(s) Affected**: tinycua

**Issue**: [#70 — Prototype M1: Basic Tools](https://github.com/VJyzCELERY/TINYCUA/issues/70)
**Parent Roadmap**: [#60 — TINYCUA Minimal Prototype](https://github.com/VJyzCELERY/TINYCUA/issues/60)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide the foundational tool layer that the Task Executor, Task Analyzer, and other agents will use to interact with the environment. After M1, the prototype can execute sandboxed local tool actions and return structured observations — no agents, graph orchestration, or session-dependent state are required yet.
- **Gaps**: The architecture has design docs for task tools, todo tools, digester tools, and tool constants, but these remain unimplemented as callable code. The `native_tools` spec covers only shell/file/web/python execution; the broader tool ecosystem (task read/write, todo, digester interface, tool result model, SDK wrappers) has no implementation spec.
- **Non-Goals**: Agent execution, custom loops, AgentNode classes, graph orchestration, CLI, and WildClawBench batch runner. Durable persistence of tool results. **Session-dependent tools (TodoList, digester retrieval interface, per-agent tool constants) are deferred to M2** — M1 delivers only stateless tool primitives. Full browser/GUI automation unless required for the selected benchmark subset; if required, only define the minimal adapter contract and complete benchmark-specific support in a later milestone.
- **Constraints**: All tools must be implemented as `tinycua_sdk` `@tool`-decorated functions compatible with the SDK's `Agent` and `AgentExecutor`. Must work with both local (LM Studio) and remote (OpenAI) providers. Must be safe for benchmark execution (no arbitrary code execution without boundaries).

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A future Task Executor agent receives a benchmark task (e.g., "read the file at /data/input.csv, compute the average of column 'price', and write the result to /data/output.txt"). The agent uses native tools (`read_file`, `run_shell`, `run_python`, `write_file`) to execute the work. All tool calls produce structured output the agent can interpret.

### Acceptance Scenarios

1. **Given** a shell execution tool, **When** called with a valid command, **Then** it returns `{stdout, stderr, exit_code, timed_out, error}`.
2. **Given** a file read tool, **When** called with a valid path, **Then** the file contents are returned as a string (truncated if over limit).
3. **Given** a file write tool, **When** called with a path and content, **Then** the file is created or overwritten and a success confirmation is returned.
4. **Given** an HTTP fetch tool, **When** called with a valid URL, **Then** the response body is returned (truncated if too large).
5. **Given** a Python execution tool, **When** called with valid code, **Then** it executes and returns `{stdout, stderr, exit_code}`.
6. **Given** the `ToolResult` model, **When** instantiated with tool output, **Then** the result is a JSON-serializable value usable by future `ExecutionLog`.
7. **Given** any tool call, **When** the agent receives the tool result, **Then** the result is a JSON-serializable value that the SDK can normalize for the LLM.

### Edge Cases

- What happens when `run_shell` command times out or does not exist?
- What happens when `read_file` is given a path that does not exist or is a directory?
- What happens when `fetch_url` receives a non-200 response or invalid URL?
- What happens when `run_python` code has a syntax error or infinite loop?
- What happens when large outputs are returned (file too large, URL response too large)?

---

## Requirements _(mandatory)_

### Non-Functional Requirements

- **NFR-001 — Concurrency Model**: Tool execution need not be thread-safe for M1. Each agent loop executes tools sequentially within a single session. If concurrent execution is introduced later, session state access must be protected.
- **NFR-002 — Task Tree Scale**: Not applicable to M1 (task tools deferred to M2).
- **NFR-003 — Tool Call Latency**: Native execution tools (shell, file, web, python) should return within their configured timeout.
- **NFR-004 — Idempotency**: Read-only tools (read_file, list_files) MUST be idempotent. Write tools are NOT required to be idempotent.
- **NFR-005 — Determinism**: Tool results for the same inputs and same session state MUST be deterministic (except run_shell, run_python, fetch_url which depend on external systems).

### Functional Requirements

#### Native Tool Result Model

- **FR-001**: System MUST provide a structured `ToolResult` model with fields: `success` (bool), `output` (str), `error` (str | None), `metadata` (dict), `duration` (float). This model MUST be usable by future `ExecutionLog`.

> **Note**: FR-002 through FR-007 describe native execution tools (shell, file I/O, HTTP, Python).
> These tools already exist in the `native_tools` specification at `src/tinycua/specs/native_tools/spec.md`
> and have implementations at `tinycua/agent/tools/native/`. For M1 Basic Tools, these will be
> adapted/verified for SDK compatibility rather than built from scratch.

#### Shell Execution Tool

- **FR-002**: System MUST provide a `run_shell` tool that executes a shell command with configurable timeout, returning `{stdout, stderr, exit_code, timed_out, error}`. *(Existing native_tools impl at `tinycua/agent/tools/native/shell.py`)*

#### File Tools

- **FR-003**: System MUST provide a `read_file` tool that reads a file at a given path and returns its contents as a string. Large files must be truncated with a clear indicator. Supports optional `start` (1-indexed line) and `offset` (line count) for range reads. *(Existing native_tools impl at `tinycua/agent/tools/native/files.py`)*
- **FR-004**: System MUST provide a `write_file` tool that creates or overwrites a file at a given path, creating parent directories if needed. Returns `{success, path, chars_written}`. *(Existing native_tools impl at `tinycua/agent/tools/native/files.py`)*
- **FR-005**: System MUST provide a `list_files` tool that lists files matching a glob pattern in a directory, returning a list of matching paths. *(Existing native_tools impl at `tinycua/agent/tools/native/files.py`)*

#### HTTP Fetch Tool

- **FR-006**: System MUST provide a `fetch_url` tool that performs an HTTP request (GET by default, configurable method and headers) and returns the response body. Large responses must be truncated. *(Existing native_tools impl at `tinycua/agent/tools/native/web.py`)*

#### Python Execution Tool

- **FR-007**: System MUST provide a `run_python` tool that executes Python code in an isolated subprocess with a configurable timeout, returning `{stdout, stderr, exit_code, timed_out, error}`. *(Existing native_tools impl at `tinycua/agent/tools/native/python_exec.py`)*

#### Tool Constants / Mappings

- **FR-008**: System SHOULD provide a `NATIVE_BASE_TOOLS` constant listing the six native execution tools (run_shell, read_file, write_file, list_files, fetch_url, run_python). This is a stateless convenience reference — no session required.
- **FR-009**: System MAY define a `READ_ONLY_TASK_TOOLS` constant as a forward reference to M2 task read tools (ReadActiveTask, ReadTask, ListTask). This is a placeholder only — not implemented until M2.

#### SDK Compatibility

- **FR-010**: All tools MUST be decorated with `@tool` from `tinycua_sdk` and return JSON-serializable output.
- **FR-011**: All tools MUST handle errors gracefully — returning error information in the tool result rather than raising unhandled exceptions.
- **FR-012**: Shell and Python execution MUST be bounded by configurable timeouts to prevent runaway processes.

> **Note — M2 Deferral**: The following tool groups are **deferred to M2** because they require session state or state objects not yet available:
> - **Task read/write tools** (`ReadActiveTask`, `ReadTask`, `ListTask`, `TaskInit`, `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, `UpdateTaskResult`, `UpdateActiveTaskResult`) — depend on `Task`/`TaskResult` state objects in the SDK.
> - **TodoList tool** — depends on `session.todo_list`.
> - **Digester retrieval tool interface** — depends on session context cache.
> - **Per-agent `*_BASE_TOOLS` constants** (all constants referencing session-dependent tools or agent nodes).
>
> See `src/tinycua/specs/basic-tools/design.md` for the deferred design.

### Key Entities

- **ToolResult**: A structured model with `success`, `output`, `error`, `metadata`, `duration`. Native result format for all tool executions, usable by ExecutionLog.
- **Native execution tools**: `run_shell`, `read_file`, `write_file`, `list_files`, `fetch_url`, `run_python` — stateless tool primitives that require no session state.
- **Tool constants** (M1-scoped): `NATIVE_BASE_TOOLS` (native tools list), `READ_ONLY_TASK_TOOLS` (forward reference, M2).

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Native tool result model exists**: `ToolResult` is importable from `tinycua.tools` and has all required fields.
- [ ] **All native execution tools work**: `run_shell`, `read_file`, `write_file`, `list_files`, `fetch_url`, `run_python` all return correct structured results for valid inputs.
- [ ] **Errors handled gracefully**: Each tool returns structured error information for invalid inputs, timeouts, and edge cases — no unhandled exceptions.
- [ ] **Native tool constants exist**: `NATIVE_BASE_TOOLS` is defined (and `READ_ONLY_TASK_TOOLS` may exist as a forward reference).
- [ ] **No session-dependent tools in M1**: TodoList, digester tools, and per-agent `*_BASE_TOOLS` are NOT implemented in M1 — deferred to M2.
- [ ] **Tool tests pass**: `cd src/tinycua && uv run pytest`
- [ ] **A future Task Executor can call the tool layer** without knowing CLI or graph internals.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Each native tool tested in isolation with mocked/isolated external dependencies (temp dirs, mock HTTP).
- Test happy paths: valid inputs produce expected structured outputs.
- Test error paths: file not found, invalid command, timeout, syntax error — all return error results.
- Test edge cases: empty file, empty command, empty URL.
- Test timeout enforcement: long-running commands and infinite loops are terminated.
- Test `ToolResult` model: all fields, `.to_dict()` serialization.

### Integration Tests

- Register all tools with a real SDK `Agent` and verify tool schema generation.
- Verify tool execution through `AgentExecutor.execute()`.
- Test end-to-end: native tools work together in a multi-step scenario.

### Manual Tests _(if applicable)_

- None required — tools are deterministic and fully testable in code.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Native Tool Result Model | TODO | To be implemented (new dataclass) |
| Shell Execution Tool | Done (native_tools) | Existing — verify SDK compat |
| File Read/Write/List Tools | Done (native_tools) | Existing — verify SDK compat |
| HTTP Fetch Tool | Done (native_tools) | Existing — verify SDK compat |
| Python Execution Tool | Done (native_tools) | Existing — verify SDK compat |
| Task Tools (Read+Write) | DEFERRED → M2 | Depends on Task/TaskResult state objects in SDK |
| TodoList Tool | DEFERRED → M2 | Depends on session.todo_list |
| Digester Tool Interface | DEFERRED → M2 | Depends on session context cache |
| Per-Agent *BASE_TOOLS Constants | DEFERRED → M2 | Reference session-dependent tools and agent nodes |
| Native Tool Constants (NATIVE_BASE_TOOLS) | TODO | Stateless tool reference list |
| SDK Tool Wrappers | TODO | Ensure all tools are @tool-decorated and SDK-compatible |

---

## Open Questions _(optional)_

1. **Should ToolResult be a Pydantic model or a simple dataclass?**
   - **Status**: Resolved → see design.md decision #2
   - **Resolution**: Dataclass with `.to_dict()` method — no Pydantic dependency.

2. **Where should the native tool result model live?**
   - **Status**: Resolved → see design.md decision #1
   - **Resolution**: `tinycua/tools/result.py` — alongside tool implementations.

---

## Review Checklist

- [x] Implementation details are advisory only (spec defines WHAT, design defines HOW)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
