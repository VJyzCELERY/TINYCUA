# Feature Specification: M1 — Basic Tools

**Status**: Draft
**Created**: 2026-06-02
**Last Updated**: 2026-06-02
**Subproject(s) Affected**: tinycua

**Issue**: [#70 — Prototype M1: Basic Tools](https://github.com/VJyzCELERY/TINYCUA/issues/70)
**Parent Roadmap**: [#60 — TINYCUA Minimal Prototype](https://github.com/VJyzCELERY/TINYCUA/issues/60)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide the foundational tool layer that the Task Executor, Task Analyzer, and other agents will use to interact with the environment, manage tasks, and track progress. After M1, the prototype can execute sandboxed local tool actions and return structured observations — no agents or graph orchestration are required yet.
- **Gaps**: The architecture has design docs for task tools, todo tools, digester tools, and tool constants, but these remain unimplemented as callable code. The `native_tools` spec covers only shell/file/web/python execution; the broader tool ecosystem (task read/write, todo, digester interface, tool result model, SDK wrappers) has no implementation spec.
- **Non-Goals**: Agent execution, custom loops, AgentNode classes, graph orchestration, CLI, and WildClawBench batch runner. Durable persistence of tool results. Full browser/GUI automation unless required for the selected benchmark subset; if required, only define the minimal adapter contract and complete benchmark-specific support in a later milestone.
- **Constraints**: All tools must be implemented as `tinycua_sdk` `@tool`-decorated functions compatible with the SDK's `Agent` and `AgentExecutor`. Must work with both local (LM Studio) and remote (OpenAI) providers. Must be safe for benchmark execution (no arbitrary code execution without boundaries).

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A future Task Executor agent receives a benchmark task (e.g., "read the file at /data/input.csv, compute the average of column 'price', and write the result to /data/output.txt"). The agent uses native tools (`read_file`, `run_shell`, `run_python`, `write_file`) to execute the work and uses the `TodoList` tool to track its progress during execution. All tool calls produce structured output the agent can interpret.

### Acceptance Scenarios

1. **Given** a shell execution tool, **When** called with a valid command, **Then** it returns `{stdout, stderr, exit_code, timed_out, error}`.
2. **Given** a file read tool, **When** called with a valid path, **Then** the file contents are returned as a string (truncated if over limit).
3. **Given** a file write tool, **When** called with a path and content, **Then** the file is created or overwritten and a success confirmation is returned.
4. **Given** an HTTP fetch tool, **When** called with a valid URL, **Then** the response body is returned (truncated if too large).
5. **Given** a Python execution tool, **When** called with valid code, **Then** it executes and returns `{stdout, stderr, exit_code}`.
6. **Given** the `TodoList` tool, **When** used to add/read/update/clear items, **Then** it maintains per-session short-term goal tracking.
7. **Given** the tool constants module, **When** imported, **Then** it provides pre-configured `*_BASE_TOOLS` lists for each agent node type.
8. **Given** any tool call, **When** the agent receives the tool result, **Then** the result is a JSON-serializable value that the SDK can normalize for the LLM.

### Edge Cases

- What happens when `run_shell` command times out or does not exist?
- What happens when `read_file` is given a path that does not exist or is a directory?
- What happens when `fetch_url` receives a non-200 response or invalid URL?
- What happens when `run_python` code has a syntax error or infinite loop?
- What happens when `TodoList` is called before initialization?
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

#### TodoList Tool

- **FR-008**: System MUST provide a `TodoList` tool with sub-commands: `add`, `read`, `mark_complete`, `mark_incomplete`, `edit`, `delete`, `clear`. Stored per-session on `session.todo_list`. Included in `SHARED_AGENT_BASE_TOOLS`.

#### Digester Retrieval Tool Interface

- **FR-009**: System MUST provide a digester retrieval tool interface with:
  - `create_enhanced_context_retrieval(cache_path, model, exploration_tools)` — A factory function that accepts a `cache_path` (str), `model` (LanguageModel from SDK), and `exploration_tools` (list of Tool). Returns a `Tool` instance. When called, the returned tool spawns inner transient retrieval agents to gather context, then caches and returns the result.
  - `digest_information(context_summary, key_points, advisory_instructions, constraints, known_gaps)` — Produces a structured digest string prefixed with `DIGEST_INFO::`. Accepts: `context_summary` (str), `key_points` (list[str]), `advisory_instructions` (str | None), `constraints` (list[str] | None), `known_gaps` (list[str] | None). Returns a str.

#### Tool Constants / Mappings

- **FR-010**: System MUST provide module-level `*_BASE_TOOLS` constants for each agent node type (QueryAnalyst, InformationDigester, TaskAnalyzer, TaskAssessor, TaskExecutor, ResultReviewer, PrimaryAgent) as specified in `docs/design/constants/tools.md`.

#### SDK Compatibility

- **FR-011**: All tools MUST be decorated with `@tool` from `tinycua_sdk` and return JSON-serializable output.
- **FR-012**: All tools MUST handle errors gracefully — returning error information in the tool result rather than raising unhandled exceptions.
- **FR-013**: Shell and Python execution MUST be bounded by configurable timeouts to prevent runaway processes.

> **Note — M2 Deferral**: Task read/write tools (`ReadActiveTask`, `ReadTask`, `ListTask`, `TaskInit`, `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, `UpdateTaskResult`, `UpdateActiveTaskResult`) are **deferred to M2**. The `tinycua-sdk` does not currently export `Task` or `TaskResult` classes — only `Session` with a dict-based `task_tree`. The task tools depend on proper state objects that will be implemented in M2. See `src/tinycua/specs/basic-tools/design.md` for the deferred design.

### Key Entities

- **ToolResult**: A structured model with `success`, `output`, `error`, `metadata`, `duration`. Native result format for all tool executions, usable by ExecutionLog.
- **TodoList**: A per-session flat list of `{status, todo}` items representing the agent's short-term work-in-progress tracking.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Native tool result model exists**: `ToolResult` is importable from `tinycua.tools` and has all required fields.
- [ ] **All native execution tools work**: `run_shell`, `read_file`, `write_file`, `list_files`, `fetch_url`, `run_python` all return correct structured results for valid inputs.
- [ ] **Errors handled gracefully**: Each tool returns structured error information for invalid inputs, timeouts, and edge cases — no unhandled exceptions.
- [ ] **TodoList tool works**: Add, read, mark, edit, delete, clear all operate correctly on `session.todo_list`.
- [ ] **Tool constants module exists**: All `*_BASE_TOOLS` constants are defined and importable.
- [ ] **Digester retrieval tool interface exists**: `create_enhanced_context_retrieval` and `digest_information` are defined.
- [ ] **Tool tests pass**: `cd src/tinycua && uv run pytest tests/test_tools* tests/test_todo*`
- [ ] **A future Task Executor can call the tool layer** without knowing CLI or graph internals.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Each native tool tested in isolation with mocked/isolated external dependencies (temp dirs, mock HTTP).
- Test happy paths: valid inputs produce expected structured outputs.
- Test error paths: file not found, invalid command, timeout, syntax error — all return error results.
- Test edge cases: empty file, empty command, empty URL.
- Test timeout enforcement: long-running commands and infinite loops are terminated.
- Test TodoList: all 7 sub-commands, pre-initialization behavior, empty list handling.

### Integration Tests

- Register all tools with a real SDK `Agent` and verify tool schema generation.
- Verify tool execution through `AgentExecutor.execute()`.
- Test end-to-end: native tools + todo tool work together in a multi-step scenario.

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
| TodoList Tool | TODO | Per-session short-term goal tracking |
| Digester Tool Interface | TODO | create_enhanced_context_retrieval + digest_information |
| Tool Constants | TODO | *_BASE_TOOLS mappings for all agent nodes |
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
