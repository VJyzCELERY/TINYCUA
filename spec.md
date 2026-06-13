# Feature Specification: WildClawBench TinyCUA BaseAgent Adapter

**Status**: Draft
**Created**: 2026-06-14
**Last Updated**: 2026-06-14
**Subproject(s) Affected**: tinycua (src/tinycua)
**Milestone**: 5.2 — WildClawBench TinyCUA BaseAgent Adapter
**Tracking Issue**: https://github.com/VJyzCELERY/TINYCUA/issues/87

> **Path convention**: All paths in this document are relative to the `tinycua` subproject root (`src/tinycua/`).

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a `TinyCUAAgent` adapter that implements WildClawBench's `BaseAgent` interface so TinyCUA can be selected as an agent backend for benchmark task execution.
- **Gaps**: Today, TinyCUA has a CLI entry point (`tinycua run`) and a `create_tinycua_agent()` factory, but no WildClawBench-compatible adapter. WildClawBench expects agents to implement `BaseAgent` with `run_task(spec)`, `collect_usage()`, `expects_gateway`, and `transcript_container_path`. Without this adapter, TinyCUA cannot be evaluated against the WildClawBench 60-task suite.
- **Non-Goals**:
  - Docker image or container build (covered in Milestone 5.3).
  - Full 60-task benchmark run or smoke runs (covered in Milestones 5.5/5.6).
  - WildClawBench fork management — the adapter lives in the TinyCUA codebase, not in WildClawBench itself.
  - Transcript/usage/artifact compatibility beyond what `collect_usage()` and `prepare_grading_transcript()` require (covered in Milestone 5.4).
  - Modifying `tinycua-sdk` public APIs.
- **Constraints**:
  - Must implement WildClawBench `BaseAgent` interface exactly as defined in `src/agents/base.py`.
  - Must use local model endpoints (no OpenRouter dependency).
  - Must not modify WildClawBench task definitions or grading functions.
  - Must preserve transcripts, logs, and task outputs for failure analysis.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

WildClawBench's `run_batch.py` selects TinyCUA as an agent backend. It constructs an `AgentTaskSpec` with task prompt, workspace path, timeout, output directory, and model configuration. It calls `agent.run_task(spec)` which starts a subprocess running the TinyCUA CLI (or factory), waits for completion or timeout, and returns an `AgentExecution` with timing and error state. After the task, `collect_usage()` is called to gather token/cost data, and `prepare_grading_transcript()` returns the path to the transcript JSONL file.

### Acceptance Scenarios

1. **Given** a `TinyCUAAgent` instance, **When** `expects_gateway` is accessed, **Then** it returns `False` (TinyCUA does not need a long-running gateway process).

2. **Given** a `TinyCUAAgent` instance, **When** `transcript_container_path` is accessed, **Then** it returns a string path to the transcript file inside the container (e.g., `/tmp_workspace/results/transcript.jsonl`).

3. **Given** a `TinyCUAAgent` instance and a valid `AgentTaskSpec`, **When** `run_task(spec)` is called, **Then** it spawns a subprocess running `tinycua run <prompt>` with the correct timeout, workspace, and output directory, and returns an `AgentExecution` with `elapsed_time` and no error.

4. **Given** a `TinyCUAAgent` instance and a valid `AgentTaskSpec`, **When** `run_task(spec)` completes, **Then** a transcript JSONL file exists at `spec.output_dir / "transcript.jsonl"` and a log file at `spec.output_dir / "agent.log"`.

5. **Given** a `TinyCUAAgent` instance, a completed task, and an output directory, **When** `collect_usage(task_id, output_dir, elapsed_time)` is called, **Then** it returns a dict containing usage data (request count, tokens if available, cost set to local-model conventions).

6. **Given** a `TinyCUAAgent` instance and a task_id, **When** `prepare_grading_transcript(task_id)` is called, **Then** it returns the `transcript_container_path` string.

7. **Given** a `TinyCUAAgent` instance and an `AgentTaskSpec` with a timeout of 30 seconds, **When** the agent does not complete within 30 seconds, **Then** `run_task(spec)` terminates the subprocess and returns an `AgentExecution` with `error` set.

8. **Given** a `TinyCUAAgent` instance and an `AgentTaskSpec` pointing to a nonexistent workspace, **When** `run_task(spec)` is called, **Then** the workspace is created before execution begins.

### Edge Cases

- What happens when `tinycua run` is not installed or not on PATH? `run_task()` returns an `AgentExecution` with an error message.
- What happens when the output directory is not writable? `run_task()` returns an error before spawning the subprocess.
- What happens when the subprocess is killed by a signal? `run_task()` captures the signal and sets `error` appropriately.
- What happens when `collect_usage()` is called before `run_task()`? Returns a dict with zeroed usage values.
- What happens when `models_config` or `lobster` fields are provided in `AgentTaskSpec`? They are ignored for now (local model only), but logged for future reference.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a `TinyCUAAgent` class that inherits from WildClawBench `BaseAgent` (or implements the same interface if importing from WildClawBench is not possible).
- **FR-002**: `expects_gateway` MUST return `False`.
- **FR-003**: `transcript_container_path` MUST return a string path to the transcript JSONL file inside the runtime container.
- **FR-004**: `run_task(spec: AgentTaskSpec) -> AgentExecution` MUST spawn a subprocess running `tinycua run <spec.prompt>` with the timeout, workspace, and output directory from the spec.
- **FR-005**: `run_task()` MUST set the working directory for the subprocess (e.g., via `Popen`'s `cwd` parameter) to `spec.workspace_path` before agent execution, so the agent operates in the task workspace.
- **FR-006**: `run_task()` MUST terminate the subprocess if it exceeds `spec.timeout_seconds` and return an `AgentExecution` with `error` set.
- **FR-007**: `run_task()` MUST return an `AgentExecution` with `elapsed_time` set to the wall-clock time of the task execution.
- **FR-008**: `collect_usage(task_id, output_dir, elapsed_time) -> dict` MUST return a dict with at minimum `{"requests": int, "total_tokens": int | None, "cost": float}`. For local model endpoints, `cost` MUST return `0.0`.
- **FR-009**: `prepare_grading_transcript(task_id) -> str` MUST return the `transcript_container_path` value.
- **FR-010**: The adapter MUST use the model configuration from `spec.model` and `spec.models_config` (or fall back to environment variables / defaults).
- **FR-011**: The adapter MUST ensure the output directory exists before execution and write `agent.log` and `transcript.jsonl` there.
- **FR-012**: The adapter MUST NOT depend on OpenRouter. All model calls must go through the local endpoint configured via `spec.model` or environment variables.

### Key Entities

- **TinyCUAAgent**: The adapter class implementing WildClawBench `BaseAgent`. Wraps the TinyCUA CLI/factory to run tasks in a subprocess.
- **AgentTaskSpec**: WildClawBench-provided dataclass with `task_id`, `task`, `prompt`, `workspace_path`, `output_dir`, `timeout_seconds`, `model`, and optional fields (`thinking`, `models_config`, `lobster`).
- **AgentExecution**: WildClawBench-provided dataclass returned by `run_task()` with `elapsed_time`, `error`, and optional process handles.
- **Usage dict**: Dictionary returned by `collect_usage()` with request count, token count, and cost.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **TinyCUAAgent class exists**: A `TinyCUAAgent` class is defined in `tinycua/wildclawbench/agent.py` (or equivalent path).
- [ ] **BaseAgent interface implemented**: All abstract methods (`expects_gateway`, `transcript_container_path`, `run_task`, `collect_usage`) are implemented.
- [ ] **run_task spawns subprocess**: `run_task()` correctly spawns `tinycua run` with proper arguments.
- [ ] **run_task handles timeout**: Subprocess is terminated after `spec.timeout_seconds`.
- [ ] **run_task returns AgentExecution**: Correct timing and error reporting.
- [ ] **collect_usage returns usage dict**: Dict contains `requests`, `total_tokens`, and `cost` keys.
- [ ] **prepare_grading_transcript returns path**: Returns `transcript_container_path`.
- [ ] **Unit tests pass**: Tests for adapter class, subprocess spawning, timeout handling, usage collection.
- [ ] **Integration test passes**: End-to-end test with a mock task spec completes successfully.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test `TinyCUAAgent.expects_gateway` returns `False`.
- Test `TinyCUAAgent.transcript_container_path` returns correct path string.
- Test `TinyCUAAgent.prepare_grading_transcript()` returns `transcript_container_path`.
- Test `TinyCUAAgent.run_task()` spawns correct subprocess command with prompt, timeout, workspace, output dir.
- Test `TinyCUAAgent.run_task()` returns `AgentExecution` with correct `elapsed_time`.
- Test `TinyCUAAgent.run_task()` terminates subprocess on timeout and sets `error`.
- Test `TinyCUAAgent.run_task()` creates output directory if it doesn't exist.
- Test `TinyCUAAgent.run_task()` returns error when subprocess fails.
- Test `TinyCUAAgent.collect_usage()` returns dict with expected keys.
- Test `TinyCUAAgent.collect_usage()` returns zeroed values when called before `run_task()`.

### Integration Tests

- Test end-to-end: create agent, run a simple prompt through `run_task()`, verify transcript and log files exist.
- Test timeout: run with a very short timeout, verify agent terminates and returns error.

### Manual Tests

- Verify adapter works with WildClawBench `run_batch.py` by running a single task.
- Verify transcript output is valid JSONL and can be parsed by WildClawBench transcript loader.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| TinyCUAAgent class definition | TODO | New module — see design.md |
| BaseAgent interface implementation | TODO | Depends on class definition |
| Subprocess spawning logic | TODO | Core run_task implementation — see design.md Decision #1 |
| Timeout handling | TODO | Popen communicate(timeout=) — see design.md Decision #3 |
| Usage collection | TODO | Transcript JSONL parsing — see design.md Decision #4 |
| Transcript path management | TODO | See design.md Decision #5; tracking continues in task.md |
| Unit tests | TODO | See implementation-plan.md |
| Integration tests | TODO | See implementation-plan.md |

---

## Open Questions _(optional)_

1. **Should the adapter live inside `src/tinycua/` or in a separate package?**
   - **Owner**: @VJyzCELERY
   - **Status**: Proposed
   - **Proposed Answer**: Inside `src/tinycua/tinycua/wildclawbench/` as a subpackage, keeping the adapter code co-located with the agent it wraps.

2. **Should `run_task()` use the CLI entry point (`tinycua run`) or call `create_tinycua_agent()` directly?**
   - **Owner**: @VJyzCELERY
   - **Status**: Proposed
   - **Proposed Answer**: Use the CLI entry point (`tinycua run`) as a subprocess, because WildClawBench expects process-level isolation and the CLI already handles timeout, workspace, output, and transcript writing. This matches how other WildClawBench backends work.

---

## Review Checklist

- [ ] No implementation details beyond what the design docs specify
- [ ] All mandatory sections completed
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
- [ ] Exit criteria match Milestone 5.2 from the roadmap issue
