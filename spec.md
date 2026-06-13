# Feature Specification: TinyCUA CLI / Runtime Entry Point for Benchmark Tasks

**Status**: Draft
**Created**: 2026-06-13
**Last Updated**: 2026-06-13
**Subproject(s) Affected**: tinycua (src/tinycua)
**Milestone**: 5.1 — TinyCUA CLI / Runtime Entry Point for Benchmark Tasks
**Tracking Issue**: https://github.com/VJyzCELERY/TINYCUA/issues/87

> **Path convention**: All paths in this document are relative to the `tinycua` subproject root (`src/tinycua/`). For example, `cli/entry.py` maps to `src/tinycua/tinycua/cli/entry.py`.

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a stable CLI entry point that WildClawBench can invoke to run TinyCUA agent tasks, accepting a task prompt and timeout, running inside a benchmark container, and producing transcript/log artifacts for grading.
- **Gaps**: Today TinyCUA has no CLI interface — it can only be invoked programmatically via `create_tinycua_agent(...)` and `.run(...)`. WildClawBench requires a command-line entry point that accepts task prompts and runs inside Docker containers with `/tmp_workspace` as the working directory.
- **Non-Goals**:
  - Production-quality CLI/TUI UX (rich output, interactive mode, progress bars).
  - WildClawBench BaseAgent adapter (covered in Milestone 5.2).
  - Docker image creation (covered in Milestone 5.3).
  - Transcript/usage artifact collection for WildClawBench grading (covered in Milestone 5.4).
  - Modifying `tinycua-sdk` public APIs.
- **Constraints**:
  - Must not modify `tinycua-sdk` public APIs.
  - Must accept task prompt and timeout as primary inputs.
  - Must use `/tmp_workspace` as working directory when available (benchmark container convention).
  - Must write required outputs to `/tmp_workspace/results` when task prompt requires it.
  - Must use local model endpoint configuration (not OpenRouter).
  - Must produce transcript/log artifacts suitable for post-run analysis.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A WildClawBench benchmark runner (or a human developer testing locally) invokes TinyCUA via a CLI command with a task prompt. The CLI creates a `create_tinycua_agent(...)`, runs it with the provided prompt, respects a timeout, and writes output artifacts (transcript, logs) to a specified directory. The agent operates within `/tmp_workspace` as its working directory.

### Acceptance Scenarios

1. **Given** a task prompt "Create a Python script that prints hello world", **When** the CLI is invoked with `tinycua run --prompt "Create a Python script that prints hello world" --timeout 120`, **Then** the agent processes the task, produces output files in `/tmp_workspace/results`, and exits with code 0.

2. **Given** a task prompt and a timeout of 60 seconds, **When** the agent exceeds the timeout, **Then** the CLI terminates the run gracefully, writes partial transcript/logs, and exits with a timeout-specific exit code.

3. **Given** a task prompt, **When** the CLI is invoked with `--workspace /custom/path`, **Then** the agent uses `/custom/path` as its working directory instead of `/tmp_workspace`.

4. **Given** a task prompt, **When** the CLI is invoked with `--output-dir /tmp_workspace/results`, **Then** transcript and log artifacts are written to that directory.

5. **Given** a task prompt, **When** the CLI is invoked with `--model-endpoint http://localhost:8080/v1`, **Then** the agent uses the specified local model endpoint for all LLM calls.

6. **Given** a task prompt, **When** the CLI is invoked with `--verbose`, **Then** additional debug output is written to stderr.

7. **Given** an invalid task prompt (empty string), **When** the CLI is invoked, **Then** it exits with a clear error message and non-zero exit code.

8. **Given** a task prompt, **When** the agent completes successfully, **Then** the CLI writes a `run_summary.json` containing task status, elapsed time, and artifact paths.

### Edge Cases

- What happens when `/tmp_workspace` does not exist? (Create it, or fail with a clear error message.)
- What happens when the local model endpoint is unreachable? (Exit with connection error and non-zero code.)
- What happens when the timeout is 0? (Immediate timeout — exit immediately.)
- What happens when `--output-dir` is not writable? (Exit with permission error.)
- What happens when the agent raises an unhandled exception? (Catch, log, write partial artifacts, exit with error code.)

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: CLI MUST accept a task prompt via `--prompt` flag or stdin.
- **FR-002**: CLI MUST accept a timeout in seconds via `--timeout` flag (default: 300).
- **FR-003**: CLI MUST accept a workspace directory via `--workspace` flag (default: `/tmp_workspace`).
- **FR-004**: CLI MUST accept an output directory via `--output-dir` flag (default: `<workspace>/results`).
- **FR-005**: CLI MUST accept a local model endpoint via `--model-endpoint` flag (default: from environment or config).
- **FR-006**: CLI MUST accept a verbose flag (`--verbose`) for debug output.
- **FR-007**: CLI MUST create a `create_tinycua_agent(...)` with the specified model endpoint and session configuration.
- **FR-008**: CLI MUST run the agent with the provided prompt and respect the timeout.
- **FR-009**: CLI MUST write transcript artifacts (JSONL event log) to the output directory.
- **FR-010**: CLI MUST write a `run_summary.json` with task status, elapsed time, and artifact paths.
- **FR-011**: CLI MUST exit with code 0 on successful completion, code 1 on agent error, code 2 on timeout, and code 3 on configuration error.
- **FR-012**: CLI MUST use `/tmp_workspace` as the working directory when no `--workspace` is specified.
- **FR-013**: CLI MUST create the workspace and output directories if they do not exist.
- **FR-014**: CLI MUST handle SIGINT/SIGTERM gracefully, writing partial artifacts before exit.

### Key Entities

- **RunConfig**: Configuration dataclass holding CLI arguments (prompt, timeout, workspace, output_dir, model_endpoint, verbose).
- **RunSummary**: Result dataclass holding run outcome (status, elapsed_time, artifact_paths, error_message).
- **CLI**: The command-line interface entry point (`tinycua run` or `python -m tinycua.cli`).

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **CLI accepts task prompt**: `tinycua run --prompt "..."` invokes the agent with the specified prompt.
- [ ] **CLI respects timeout**: Agent is terminated after the specified timeout with graceful shutdown.
- [ ] **CLI uses correct workspace**: Agent operates within the specified workspace directory.
- [ ] **CLI writes output artifacts**: Transcript JSONL and `run_summary.json` are written to the output directory.
- [ ] **CLI handles errors gracefully**: Invalid inputs, unreachable endpoints, and agent exceptions produce clear error messages and appropriate exit codes.
- [ ] **CLI creates directories**: Workspace and output directories are created if they do not exist.
- [ ] **CLI handles signals**: SIGINT/SIGTERM trigger graceful shutdown with partial artifact writing.
- [ ] **CLI supports local model endpoint**: Agent uses the specified endpoint for all LLM calls.
- [ ] **Tests pass**: Unit tests for CLI argument parsing, RunConfig creation, RunSummary generation, and timeout handling.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test CLI argument parsing for all flags (--prompt, --timeout, --workspace, --output-dir, --model-endpoint, --verbose).
- Test RunConfig creation from parsed arguments with defaults.
- Test RunSummary generation for success, error, and timeout cases.
- Test directory creation logic (workspace and output).
- Test timeout handling with mock agent.
- Test signal handling (SIGINT/SIGTERM) with graceful shutdown.

### Integration Tests

- Test full CLI invocation with a mock agent that completes successfully.
- Test full CLI invocation with a mock agent that times out.
- Test full CLI invocation with a mock agent that raises an exception.
- Test artifact writing (transcript JSONL and run_summary.json) end-to-end.

### Manual Tests

- Verify CLI help output (`tinycua run --help`) shows all flags with descriptions.
- Verify CLI works with a real local model endpoint (e.g., Ollama or vLLM).
- Verify artifacts are written correctly to the output directory.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| CLI argument parsing | TODO | -- |
| RunConfig dataclass | TODO | -- |
| RunSummary dataclass | TODO | -- |
| Agent factory integration | TODO | Uses create_tinycua_agent() |
| Timeout handling | TODO | -- |
| Artifact writing | TODO | Transcript JSONL + run_summary.json |
| Signal handling | TODO | SIGINT/SIGTERM graceful shutdown |
| Unit tests | TODO | -- |
| Integration tests | TODO | -- |

---

## Open Questions _(optional)_

1. **Should the CLI support reading prompt from a file (not just --prompt or stdin)?**
   - **Owner**: @VJyzCELERY
   - **Status**: Proposed
   - **Proposed Answer**: Not in this milestone. Keep it simple — --prompt and stdin are sufficient for WildClawBench.

2. **Should the CLI support multiple model endpoints (e.g., separate judge-LLM)?**
   - **Owner**: @VJyzCELERY
   - **Status**: Proposed
   - **Proposed Answer**: Not in this milestone. Judge-LLM configuration can be managed later.

---

## Review Checklist

- [ ] No implementation details beyond what the design docs specify
- [ ] All mandatory sections completed
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
- [ ] Exit criteria match Milestone 5.1 from the roadmap issue
