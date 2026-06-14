# Feature Specification: Full 60-Task Local-LLM Benchmark Run

**Status**: Draft
**Created**: 2026-06-14
**Last Updated**: 2026-06-14
**Subproject(s) Affected**: tinycua (src/tinycua)
**Milestone**: 5.6 — Full 60-Task Local-LLM Benchmark Run
**Tracking Issue**: https://github.com/VJyzCELERY/TINYCUA/issues/87

> **Path convention**: All paths in this document are relative to the `tinycua` subproject root (`src/tinycua/`).

---

## Problem Statement _(mandatory)_

- **Goals**: Execute all 60 WildClawBench tasks using the TinyCUA harness with a local LLM model, producing aggregate results (`summary_all.json`) that enable comparison with other harnesses.
- **Gaps**: Prior milestones (5.1–5.5) established the CLI entry point, BaseAgent adapter, Docker image, transcript/usage compatibility, and smoke runs. This milestone scales to the full task suite to produce benchmark data for analysis.
- **Non-Goals**:
  - Benchmark analysis or comparison reports (covered in Milestone 5.7).
  - Modifying WildClawBench tasks or grading functions.
  - Hosted/cloud model benchmarking — all runs use local LLM endpoints.
  - Judge LLM subscription management.
  - Code changes to TinyCUA architecture (the focus is execution and data collection).
- **Constraints**:
  - Must use the existing `TinyCUAAgent` adapter from Milestone 5.2.
  - Must use the Docker image from Milestone 5.3.
  - Must use local LLM model endpoints (no OpenRouter).
  - Must preserve all task-level artifacts for failure analysis.
  - Must write results to benchmark_results/ directory at the tinycua subproject root.
  - benchmark_results/ MUST be gitignored to prevent accidental commits of large artifact files.
  - Must record local model, endpoint, hardware, runtime, and judge configuration.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A researcher configures a local LLM endpoint (e.g., vLLM, Ollama, LM Studio), builds the TinyCUA Docker image, and runs the full WildClawBench benchmark suite. The system executes all 60 tasks, collects scores, usage data, transcripts, and task outputs, and produces a `summary_all.json` aggregate results file.

### Acceptance Scenarios

1. **Given** a configured local LLM endpoint and the TinyCUA Docker image, **When** the full benchmark run is initiated, **Then** all 60 WildClawBench tasks are executed against the TinyCUA harness.

2. **Given** a completed benchmark run, **When** the results are inspected, **Then** a `summary_all.json` file exists containing aggregate scores, task-level results, and metadata.

3. **Given** a completed benchmark run, **When** task-level artifacts are inspected, **Then** each task has a transcript, usage data, log file, and task output (where applicable).

4. **Given** a completed benchmark run, **When** the metadata section of `summary_all.json` is inspected, **Then** it records the local model name, endpoint URL, hardware specifications, runtime version, and judge configuration.

5. **Given** a benchmark run with some task failures, **When** the results are inspected, **Then** failed tasks are clearly marked with error details, and successful tasks still have valid scores.

6. **Given** a benchmark run, **When** the output directory is inspected, **Then** the structure matches WildClawBench conventions (e.g., `results/<task_id>/transcript.jsonl`, `results/<task_id>/usage.json`, `results/<task_id>/agent.log`).

### Edge Cases

- What happens when the local LLM endpoint becomes unavailable mid-run? Tasks should fail gracefully with error details, and the run should continue with remaining tasks.
- What happens when a task exceeds its timeout? The task is marked as failed/timed-out, and the run continues.
- What happens when Docker resources are exhausted? The run should fail gracefully with resource error details.
- What happens when the output directory is not writable? The run should fail before executing any tasks with a clear error message.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST execute all 60 WildClawBench tasks using the TinyCUA harness via the `TinyCUAAgent` adapter.
- **FR-002**: System MUST produce a `summary_all.json` file containing aggregate results for all tasks.
- **FR-003**: `summary_all.json` MUST include per-task results with task_id, score, status (success/failed/timeout), elapsed_time, and error details (if any).
- **FR-004**: `summary_all.json` MUST include metadata section with: local_model_name, endpoint_url, hardware_info (CPU/GPU/RAM), runtime_version, docker_image_tag, and judge_configuration.
- **FR-005**: System MUST preserve task-level artifacts (transcript.jsonl, usage.json, agent.log, task outputs) for each task in the output directory.
- **FR-006**: System MUST record usage data (request count, tokens if available, cost=0.0 for local models) for each task.
- **FR-007**: System MUST handle task failures gracefully, recording error details and continuing with remaining tasks.
- **FR-008**: System MUST provide a summary of pass/fail/skip counts across all tasks.
- **FR-009**: System MUST use the existing `tinycua run` CLI entry point via the `TinyCUAAgent` adapter.
- **FR-010**: System MUST NOT modify WildClawBench task definitions or grading functions.
- **FR-011**: System MUST NOT depend on OpenRouter or any hosted model service.
- **FR-012**: System MUST record the start time, end time, and total duration of the benchmark run.

### Key Entities

- **BenchmarkRun**: Represents a complete 60-task execution. Contains run metadata, per-task results, and aggregate statistics.
- **TaskResult**: Per-task execution result with task_id, score, status, elapsed_time, error, and artifact paths.
- **RunMetadata**: Configuration snapshot including model name, endpoint, hardware, runtime version, and judge config.
- **SummaryAggregate**: Aggregate statistics including total tasks, pass/fail/skip counts, average score, and total duration.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

> **Note**: These criteria will be checked off as implementation progresses. All are currently unchecked because implementation has not started.

- [ ] **Full task execution**: All 60 WildClawBench tasks are executed against the TinyCUA harness.
- [ ] **summary_all.json exists**: A valid JSON file exists at the expected output path after the run.
- [ ] **Per-task results**: `summary_all.json` contains results for all 60 tasks with task_id, score, status, elapsed_time, and error fields.
- [ ] **Metadata recorded**: `summary_all.json` metadata section includes model name, endpoint, hardware, runtime version, and judge config.
- [ ] **Task artifacts preserved**: Each task directory contains transcript.jsonl, usage.json, and agent.log files.
- [ ] **Usage data collected**: Each task's usage.json contains requests, total_tokens, and cost fields.
- [ ] **Failure handling**: Failed tasks are marked with error details; successful tasks still have valid scores.
- [ ] **Aggregate statistics**: `summary_all.json` includes summary counts (total, pass, fail, skip) and average score.
- [ ] **Run timing**: Start time, end time, and total duration are recorded in metadata.
- [ ] **No OpenRouter dependency**: All model calls go through the configured local endpoint.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test `summary_all.json` schema validation (required fields, types, structure).
- Test aggregate statistics calculation (pass/fail/skip counts, average score).
- Test metadata generation (model name, endpoint, hardware info extraction).
- Test failure handling logic (timeout errors, connection errors, task failures).

### Integration Tests

- Test full benchmark run with a subset of tasks (e.g., 3-5 tasks) to verify end-to-end flow.
- Test that task artifacts are correctly generated and preserved.
- Test that `summary_all.json` is correctly written and parseable.

### Manual Tests

- Run the full 60-task benchmark with a local LLM endpoint.
- Verify `summary_all.json` contents and structure.
- Verify task-level artifacts for a sample of tasks.
- Compare results format with WildClawBench conventions.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Benchmark run script | TODO | Script to orchestrate full 60-task run |
| summary_all.json generation | TODO | Schema and generation logic |
| Metadata collection | TODO | Model, hardware, runtime info |
| Artifact preservation | TODO | Task output directory structure |
| Failure handling | TODO | Graceful error handling per task |
| Aggregate statistics | TODO | Pass/fail/skip counts, averages |
| Unit tests | TODO | Schema validation, aggregate logic |
| Integration tests | TODO | Subset run verification |

---

## Open Questions _(optional)_

1. **What local LLM model should be used for the benchmark?**
   - **Owner**: @VJyzCELERY
   - **Status**: Resolved
   - **Proposed Answer**: Use the model configured via BenchmarkConfig (default: llama3). The specific model is documented in run metadata.

2. **Should the benchmark run be executed via Docker or locally?**
   - **Owner**: @VJyzCELERY
   - **Status**: Resolved
   - **Proposed Answer**: Docker is required per the milestone constraint. The Docker image from Milestone 5.3 (tinycua-benchmark:latest) must be used.

3. **How should judge LLM configuration be handled?**
   - **Owner**: @VJyzCELERY
   - **Status**: Resolved
   - **Proposed Answer**: Judge configuration is optional and documented in RunMetadata. When not configured, judge_model and judge_endpoint are null in the metadata.

---

## Review Checklist

- [ ] No implementation details beyond what the design docs specify
- [ ] All mandatory sections completed
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
- [ ] Exit criteria match Milestone 5.6 from the roadmap issue
