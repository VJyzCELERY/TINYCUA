# Feature Specification: Native Benchmark Tools

**Status**: In Progress
**Created**: 2026-05-30
**Last Updated**: 2026-05-30
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Provide the Task Executor agent with a minimal but complete set of native tools (shell execution, file operations, web fetching, and code execution) so it can complete WildClawBench benchmark tasks.
- **Gaps**: The `src/tinycua/tinycua/agent/tools/` directory exists but contains only skeletons. No working tools are implemented.
- **Non-Goals**: Enhanced Context Retrieval (architecture-internal tool for the Information Digester — separate milestone). Agent-calling tools for sub-agent orchestration (separate milestone). Tool permissions or approval workflows beyond the SDK's built-in allow/ask/deny mechanism.
- **Constraints**: Tools must be implemented as `tinycua_sdk` `@tool`-decorated functions. Must work with both local (LM Studio) and remote (OpenAI) providers. Must be safe for benchmark execution (no arbitrary code execution without boundaries).

---

## User Scenarios & Testing

### Primary Scenario

A Task Executor agent receives a benchmark task (e.g., "read the file at /data/input.csv, compute the average of column 'price', and write the result to /data/output.txt"). The agent uses `read_file` to read the CSV, `run_python` to compute the average, and `write_file` to save the result. All tool calls produce structured output the agent can interpret.

### Acceptance Scenarios

1. **Given** a Task Executor agent with the native tools registered, **When** the agent calls `read_file` with a valid path, **Then** the file contents are returned as a string.
2. **Given** a Task Executor agent, **When** the agent calls `write_file` with a path and content, **Then** the file is created or overwritten and a success confirmation is returned.
3. **Given** a Task Executor agent, **When** the agent calls `edit_file` with a path, start line, and replacement content, **Then** the specified lines are replaced and a success confirmation is returned.
4. **Given** a Task Executor agent, **When** the agent calls `run_shell` with a valid command, **Then** the command executes and returns stdout + stderr + exit code.
5. **Given** a Task Executor agent, **When** the agent calls `fetch_url` with a valid URL, **Then** the HTTP response body is returned (truncated if too large).
6. **Given** a Task Executor agent, **When** the agent calls `run_python` with valid Python code, **Then** the code executes in a subprocess and returns stdout + stderr.
7. **Given** a Task Executor agent, **When** the agent calls `list_files` with a directory path and glob pattern, **Then** matching file paths are returned as a list.
8. **Given** any tool call, **When** the agent receives the tool result, **Then** the result is a JSON-serializable value (string, dict, or list) that the agent can interpret.

### Edge Cases

- What happens when `read_file` is given a path that does not exist?
- What happens when `write_file` is given a directory that does not exist?
- What happens when `run_shell` command times out?
- What happens when `fetch_url` receives a non-200 response or times out?
- What happens when `run_python` code has a syntax error or infinite loop?
- What happens when `list_files` is given a path that does not exist?
- What happens when `edit_file` is given a start line beyond the file's length?
- What happens when `read_file` or `edit_file` is given a `start+offset` that exceeds the file's line count?
- How are large outputs handled (file too large, URL response too large)?

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a `run_shell` tool that executes a shell command with configurable timeout, returning `{stdout, stderr, exit_code}`.
- **FR-002**: System MUST provide a `read_file` tool that reads a file at a given path and returns its contents as a string. Large files must be truncated with a clear indicator.
- **FR-003**: System MUST provide a `write_file` tool that creates or overwrites a file at a given path, creating parent directories if needed. Returns `{success, path, chars_written}`.
- **FR-004**: System MUST provide an `edit_file` tool that replaces lines in an existing file starting at a given line number. Supports an optional `offset` to limit how many lines are replaced. Returns `{success, path, start_line, lines_replaced, bytes_written}`. The file must already exist.
- **FR-005**: System MUST provide a `list_files` tool that lists files matching a glob pattern in a directory, returning a list of matching paths.
- **FR-006**: System MUST provide a `fetch_url` tool that performs an HTTP request (GET by default, configurable method and headers) and returns the response body. Large responses must be truncated.
- **FR-007**: System MUST provide a `run_python` tool that executes Python code in an isolated subprocess with a configurable timeout, returning `{stdout, stderr, exit_code}`.
- **FR-008**: All tools MUST return structured, JSON-serializable output the SDK can normalize for the LLM.
- **FR-009**: All tools MUST handle errors gracefully — returning error information in the tool result rather than raising unhandled exceptions.
- **FR-010**: Shell and Python execution MUST be bounded by configurable timeouts to prevent runaway processes.
- **FR-011**: All tools MUST be implemented as `tinycua_sdk` `@tool`-decorated functions compatible with the SDK's `Agent` and `ToolExecutor`.

### Key Entities

- **Tool Result**: A JSON-serializable value (string, dict, or list) returned by a tool. For structured tools (`run_shell`, `write_file`, `edit_file`, `run_python`), the result is a dict with success/error fields. For data tools (`read_file`, `fetch_url`, `list_files`), the result is a string or list.
- **Tool Error**: When a tool encounters an error, it returns a dict with an `error` field rather than raising. This ensures the agent can see and respond to failures.

---

## Success Criteria

- [ ] **All 7 tools are importable and callable**: Each tool function can be imported and called directly.
- [ ] **Tools work as SDK tools**: Each tool can be registered with an SDK `Agent` and invoked through `ToolExecutor`.
- [ ] **Happy-path operations succeed**: Read, write, edit, list, shell, fetch, and execute all work for valid inputs.
- [ ] **Errors are handled gracefully**: File not found, timeout, invalid URL, syntax error, invalid start line — all return structured error results, not exceptions.
- [ ] **Timeouts are enforced**: Shell and Python execution respect the configured timeout.
- [ ] **Large outputs are truncated**: Files and HTTP responses over a reasonable limit are truncated with an indicator.
- [ ] **Parent directories are created**: `write_file` creates missing parent directories automatically.

---

## Testing Plan

### Unit Tests

- Each tool tested in isolation with mocked external dependencies where appropriate (mock HTTP for `fetch_url`, temp directories for file tools).
- Test happy path: valid inputs produce expected outputs.
- Test error paths: file not found, invalid command, timeout, syntax error — all return error results.
- Test edge cases: empty file, empty command, empty URL.
- Test truncation: large files and responses are truncated.
- Test timeout: long-running commands and infinite loops are terminated.

### Integration Tests

- Register all tools with a real SDK `Agent` and verify tool schema generation.
- Verify tool execution through `ToolExecutor.execute()`.
- Test with a live LLM (optional, marked as integration) — agent uses tools to complete a simple multi-step task.

### Manual Tests

- None required — tools are deterministic and fully testable in code.
