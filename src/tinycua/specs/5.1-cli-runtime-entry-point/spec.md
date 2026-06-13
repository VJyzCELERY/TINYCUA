# Feature Specification: TinyCUA CLI / Runtime Entry Point

**Status**: Draft
**Created**: 2026-06-13
**Last Updated**: 2026-06-13
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Provide a stable CLI entry point that WildClawBench can invoke to run TinyCUA agent tasks inside a benchmark container, producing transcript/log artifacts for grading.
- **Gaps**: The current CLI is a no-op placeholder (`tinycua: workspace is ready.`). There is no mechanism to accept a task prompt and timeout, execute the TinyCUA agent with local model configuration, manage the `/tmp_workspace` working directory, or produce benchmark-compatible output artifacts.
- **Non-Goals**: Production-quality TUI/UX, HITL interrupt/resume, WildClawBench adapter implementation (Milestone 5.2), Docker image creation (Milestone 5.3), or full benchmark runs (Milestones 5.5–5.7).
- **Constraints**: Must use the existing `create_tinycua_agent()` factory and `TinyCUALoop` without SDK API modifications. Must support local OpenAI-compatible model endpoints (vLLM, Ollama, LM Studio). Must write outputs to `/tmp_workspace/results` when required by the task prompt.

---

## User Scenarios & Testing

### Primary Scenario

A WildClawBench benchmark runner (or a developer testing locally) invokes the TinyCUA CLI with a task prompt and timeout. The CLI:
1. Accepts the task prompt and timeout as command-line arguments
2. Configures the local model endpoint from environment variables or CLI flags
3. Creates a TinyCUA agent using the factory
4. Runs the agent with the provided prompt
5. Writes transcript and log artifacts to the specified output directory
6. Exits cleanly with appropriate exit codes

### Acceptance Scenarios

1. **Given** a valid task prompt and timeout, **When** the CLI is invoked, **Then** the TinyCUA agent executes the prompt and produces a transcript file at the configured output path.
2. **Given** a task prompt requiring file outputs, **When** the agent completes, **Then** the outputs are written under `/tmp_workspace/results`.
3. **Given** local model endpoint environment variables (`TINYCUA_BASE_URL`, `TINYCUA_API_KEY`), **When** the CLI starts, **Then** the agent uses the configured endpoint for all LLM calls.
4. **Given** an invalid or missing prompt, **When** the CLI is invoked, **Then** it exits with a non-zero status code and a descriptive error message.
5. **Given** the agent exceeds the timeout, **When** the timeout is reached, **Then** the CLI terminates the agent process and exits with a timeout-specific exit code.
6. **Given** a successful run, **When** the CLI exits, **Then** the exit code is 0 and transcript/log files exist in the output directory.

### Edge Cases

- What happens when the local model endpoint is unreachable? The CLI should fail fast with a clear error message and non-zero exit code.
- What happens when the output directory is not writable? The CLI should fail fast before attempting agent execution.
- What happens with an empty task prompt? The CLI should reject it with a validation error.
- What happens when the agent crashes mid-execution? The CLI should catch the exception, log it, and exit with a non-zero code while preserving any partial transcript.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST accept a task prompt as a required positional argument or `--prompt` flag.
- **FR-002**: System MUST accept a timeout in seconds via `--timeout` flag (default: 600 seconds).
- **FR-003**: System MUST accept an output directory via `--output-dir` flag (default: `/tmp_workspace/results`).
- **FR-004**: System MUST accept a working directory via `--workspace` flag (default: `/tmp_workspace`).
- **FR-005**: System MUST configure the local model endpoint from `TINYCUA_BASE_URL` and `TINYCUA_API_KEY` environment variables, with CLI override via `--base-url` and `--api-key` flags.
- **FR-006**: System MUST configure the model name from `TINYCUA_MODEL` environment variable or `--model` flag (default: a sensible local model identifier).
- **FR-007**: System MUST create a TinyCUA agent using `create_tinycua_agent()` factory.
- **FR-008**: System MUST run the agent with the provided prompt and capture the response.
- **FR-009**: System MUST write a transcript file (JSONL format) to the output directory.
- **FR-010**: System MUST write an agent log file to the output directory.
- **FR-011**: System MUST set the working directory for the agent session to the specified workspace path.
- **FR-012**: System MUST exit with code 0 on successful completion.
- **FR-013**: System MUST exit with code 1 on general errors (invalid arguments, agent crash, endpoint unreachable).
- **FR-014**: System MUST exit with code 124 on timeout (matching Unix `timeout` convention).
- **FR-015**: System MUST send SIGTERM to the agent process on timeout, followed by SIGKILL after a brief grace period.
- **FR-016**: System MUST support `--verbose` flag for debug logging output.

### Key Entities

- **Task Prompt**: The natural language instruction for the TinyCUA agent to execute.
- **Timeout**: Maximum execution time in seconds before the agent is terminated.
- **Working Directory**: The filesystem path where the agent operates (default `/tmp_workspace`).
- **Output Directory**: The filesystem path where transcript and log artifacts are written.
- **Local Model Endpoint**: An OpenAI-compatible API endpoint (base URL + API key) for LLM inference.
- **Transcript**: A JSONL file containing the conversation history between the agent and the LLM, compatible with WildClawBench grading.
- **Agent Log**: A structured log file containing execution events, timing, and error information.

---

## Success Criteria

- [ ] **CLI accepts task prompt**: `tinycua run "create a file called hello.txt"` executes the agent with the prompt.
- [ ] **CLI accepts timeout**: `tinycua run --timeout 120 "do something"` terminates after 120 seconds if not complete.
- [ ] **CLI writes transcript**: After execution, a JSONL transcript file exists in the output directory.
- [ ] **CLI writes agent log**: After execution, a structured log file exists in the output directory.
- [ ] **CLI uses local model**: With `TINYCUA_BASE_URL=http://localhost:8080/v1`, the agent sends LLM requests to the local endpoint.
- [ ] **CLI handles timeout**: When the agent exceeds the timeout, the process is killed and exit code 124 is returned.
- [ ] **CLI handles errors**: When the endpoint is unreachable, the CLI exits with code 1 and an error message.
- [ ] **CLI validates inputs**: When no prompt is provided, the CLI exits with a usage error.
- [ ] **Workspace directory is set**: The agent session's working directory is set to the specified workspace path.
- [ ] **Results directory is used**: File outputs from the agent are written under the specified results path.

---

## Testing Plan

### Unit Tests

- CLI argument parsing: verify all flags and positional arguments are correctly parsed.
- Environment variable loading: verify `TINYCUA_BASE_URL`, `TINYCUA_API_KEY`, `TINYCUA_MODEL` are read correctly.
- Exit code behavior: verify exit codes 0, 1, and 124 for success, error, and timeout scenarios.
- Timeout mechanism: verify SIGTERM/SIGKILL sequence on timeout.

### Integration Tests

- End-to-end CLI execution with a mock LLM endpoint: verify transcript and log files are produced.
- Workspace directory behavior: verify the agent operates in the correct working directory.
- Output directory creation: verify the output directory is created if it doesn't exist.

### Manual Tests

- Run `tinycua run "echo hello"` against a local LLM endpoint and verify transcript output.
- Run with `--timeout 5` against a slow prompt and verify timeout behavior.
- Run with invalid endpoint and verify error handling.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| CLI argument parsing | TODO | -- |
| Environment variable loading | TODO | -- |
| Agent factory integration | TODO | -- |
| Transcript writing | TODO | -- |
| Agent log writing | TODO | -- |
| Timeout handling | TODO | -- |
| Exit code behavior | TODO | -- |
| Unit tests | TODO | -- |
| Integration tests | TODO | -- |

---

## Open Questions

1. **Transcript format alignment**
   - **Owner**: @tinycua-team
   - **Target**: 2026-06-20
   - **Status**: Discussion
   - **Proposed Answer**: Use the OpenClaw-compatible JSONL format documented in `specs/wildclawbench-adapter/adapter-contract.md` to ensure WildClawBench grading compatibility from the start.

2. **Agent log format**
   - **Owner**: @tinycua-team
   - **Target**: 2026-06-20
   - **Status**: Discussion
   - **Proposed Answer**: Use structured JSON lines with timestamps, event types, and payloads for machine-parseable logs.

---

## Review Checklist

- [ ] No implementation details beyond what the spec requires (no framework choices, no class hierarchies)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
