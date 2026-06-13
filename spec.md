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

- **Goals**: Implement a WildClawBench-compatible BaseAgent adapter for TinyCUA so that TinyCUA can be selected as an agent backend for WildClawBench benchmark evaluation, enabling comparison with other harnesses like OpenClaw, Claude Code, Codex CLI, and Hermes Agent.
- **Gaps**: Today, TinyCUA has no integration with WildClawBench. The WildClawBench benchmark requires agents to implement a `BaseAgent` interface with specific methods for task execution, usage collection, and transcript handling. Without this adapter, TinyCUA cannot participate in WildClawBench evaluation.
- **Non-Goals**:
  - Modifying WildClawBench tasks or grading logic.
  - Implementing the full TinyCUA benchmark Docker image (covered in Milestone 5.3).
  - Running full benchmark suites (covered in Milestones 5.5 and 5.6).
  - Implementing transcript/usage artifact compatibility (covered in Milestone 5.4).
- **Constraints**:
  - Must implement the WildClawBench `BaseAgent` interface as documented in `src/agents/base.py`.
  - Must work with local model endpoints (no OpenRouter dependency).
  - Must preserve TinyCUA architecture flow while adapting to WildClawBench conventions.
  - Must not modify WildClawBench source code; adapter should work in a fork or research copy.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A WildClawBench benchmark runner selects TinyCUA as an agent backend. The runner calls `run_task(spec: AgentTaskSpec)` on the TinyCUA adapter, which executes the task using TinyCUA's architecture flow and returns an `AgentExecution` result with transcript, usage, and task output artifacts.

### Acceptance Scenarios

1. **Given** a WildClawBench task specification, **When** `TinyCUAAgent.run_task(spec)` is called, **Then** TinyCUA executes the task using its full architecture flow and returns an `AgentExecution` with status, transcript path, and output directory.
2. **Given** a completed task execution, **When** `collect_usage(task_id, output_dir, elapsed_time)` is called, **Then** the adapter returns a usage dictionary with request count, tokens (if available), and cost set to local-model conventions.
3. **Given** a task with transcript requirements, **When** the task completes, **Then** the adapter writes a transcript file to the specified `transcript_container_path` in a format compatible with WildClawBench grading.
4. **Given** a task that writes output files, **When** the task completes, **Then** output files are written under `/tmp_workspace/results` as required by the task prompt.
5. **Given** the adapter configuration, **When** `expects_gateway` is checked, **Then** it returns `False` since TinyCUA uses local model endpoints.

### Edge Cases

- What happens when the local model endpoint is unreachable? The adapter should return a failed execution status with appropriate error message.
- What happens when a task exceeds the timeout? The adapter should terminate execution and return a timeout status.
- What happens when the task prompt requires tools not available in TinyCUA? The adapter should handle tool unavailability gracefully and document limitations.
- What happens with empty or malformed task specifications? The adapter should validate input and raise appropriate errors.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST implement `TinyCUAAgent(BaseAgent)` or equivalent backend class compatible with WildClawBench's `BaseAgent` interface.
- **FR-002**: System MUST implement `run_task(spec: AgentTaskSpec) -> AgentExecution` that executes a task using TinyCUA's architecture flow.
- **FR-003**: System MUST implement `collect_usage(task_id, output_dir, elapsed_time) -> dict` that returns usage statistics.
- **FR-004**: System MUST implement `expects_gateway` property returning `False` for local model endpoint usage.
- **FR-005**: System MUST implement `transcript_container_path` property for transcript file location.
- **FR-006**: System MUST implement optional `prepare_grading_transcript(...)` for transcript format compatibility.
- **FR-007**: System MUST use `/tmp_workspace` as working directory during task execution.
- **FR-008**: System MUST write required outputs to `/tmp_workspace/results` when task prompt requires it.
- **FR-009**: System MUST use local model endpoint configuration for all TinyCUA LLM calls.
- **FR-010**: System MUST preserve TinyCUA architecture flow while adapting to WildClawBench conventions.

### Key Entities

- **TinyCUAAgent**: The adapter class implementing WildClawBench's `BaseAgent` interface, wrapping TinyCUA's agent factory and execution flow.
- **AgentTaskSpec**: WildClawBench task specification containing task prompt, timeout, workspace configuration, and grading requirements.
- **AgentExecution**: WildClawBench execution result containing status, transcript path, output directory, and execution metadata.
- **UsageDict**: Dictionary containing request count, token usage (if available), and cost information for benchmark reporting.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Adapter implements BaseAgent interface**: `TinyCUAAgent` successfully implements all required `BaseAgent` methods.
- [ ] **Task execution works**: `run_task(spec)` executes a task using TinyCUA's architecture flow and returns valid `AgentExecution`.
- [ ] **Usage collection works**: `collect_usage(...)` returns a properly formatted usage dictionary.
- [ ] **Transcript handling works**: Adapter writes transcript files in a format compatible with WildClawBench grading.
- [ ] **Local model configuration works**: Adapter uses local model endpoints without OpenRouter dependency.
- [ ] **Workspace conventions work**: Adapter uses `/tmp_workspace` and writes outputs to `/tmp_workspace/results`.
- [ ] **Error handling works**: Adapter handles timeouts, unreachable endpoints, and malformed inputs gracefully.
- [ ] **Single task selection works**: WildClawBench can select TinyCUA as an agent backend for a single task.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test `TinyCUAAgent` class instantiation and configuration.
- Test `run_task(spec)` with mock task specifications.
- Test `collect_usage(...)` with mock execution data.
- Test `expects_gateway` property returns `False`.
- Test `transcript_container_path` property returns correct path.
- Test `prepare_grading_transcript(...)` with mock transcript data.
- Test input validation for malformed task specifications.
- Test error handling for timeout scenarios.

### Integration Tests

- Test full task execution flow with a mock WildClawBench task.
- Test transcript file creation and format compatibility.
- Test usage dictionary format compatibility with WildClawBench expectations.
- Test workspace directory handling (`/tmp_workspace` and `/tmp_workspace/results`).

### Manual Tests

- Verify adapter can be instantiated and configured in a WildClawBench-like environment.
- Verify task execution produces expected output files.
- Verify transcript format is readable by WildClawBench grading functions.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| BaseAgent interface implementation | TODO | |
| run_task implementation | TODO | |
| collect_usage implementation | TODO | |
| Transcript handling | TODO | |
| Local model configuration | TODO | |
| Workspace conventions | TODO | |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **WildClawBench BaseAgent interface details**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-15
   - **Status**: Discussion
   - **Proposed Answer**: Need to inspect WildClawBench `src/agents/base.py` for exact interface requirements.

2. **Transcript format compatibility**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-15
   - **Status**: Discussion
   - **Proposed Answer**: Need to understand WildClawBench transcript loader expectations.

3. **Tool availability mapping**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-15
   - **Status**: Discussion
   - **Proposed Answer**: Need to map TinyCUA tools to WildClawBench task requirements.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
