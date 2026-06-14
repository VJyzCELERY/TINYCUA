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

- **Goals**: Execute the complete WildClawBench 60-task suite using the TinyCUA harness with a local LLM model, produce aggregate benchmark results (`summary_all.json` or equivalent), and record all relevant execution metadata for analysis.
- **Gaps**: Prior milestones (5.1–5.5) established the CLI entry point, BaseAgent adapter, Docker image, transcript/usage compatibility, and smoke runs. However, no full 60-task benchmark run has been executed. We lack a comprehensive performance baseline comparing TinyCUA to other harnesses (OpenClaw, Claude Code, Codex CLI, Hermes Agent) on the same task suite.
- **Non-Goals**:
  - Architecture changes to TinyCUA nodes or the agent loop (covered in Milestones 1–4).
  - WildClawBench adapter modifications beyond what smoke runs revealed.
  - Judge-LLM configuration management (handled separately by the user).
  - Production-quality result visualization or dashboards.
  - Modifying WildClawBench tasks or grading functions.
  - Modifying `tinycua-sdk` public APIs.
- **Constraints**:
  - Must use local LLM model endpoints only (no OpenRouter dependency).
  - Must preserve all task-level artifacts, transcripts, logs, and output summaries for failure analysis.
  - Must record local model name, endpoint URL, hardware specs, runtime duration, and judge configuration.
  - Must not hide benchmark failures — all task outcomes (success, failure, timeout) must be captured.
  - Must produce a `summary_all.json` or equivalent aggregate results file.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A researcher configures TinyCUA with a local LLM endpoint (e.g., vLLM, Ollama, LM Studio), runs the full WildClawBench 60-task suite through the TinyCUA harness, and receives aggregate results in `summary_all.json` along with per-task transcripts, logs, and usage data. The researcher then uses these artifacts to compare TinyCUA's performance against other harnesses.

### Acceptance Scenarios

1. **Given** TinyCUA is configured with a valid local LLM endpoint, **When** the full 60-task benchmark run is initiated, **Then** all 60 WildClawBench tasks are executed sequentially (or with controlled concurrency) and each task produces a transcript, log, and usage artifact.

2. **Given** a completed benchmark run, **When** the researcher inspects the output directory, **Then** a `summary_all.json` file exists containing aggregate results including per-task scores, timing, token usage, and error status.

3. **Given** a completed benchmark run, **When** any individual task is examined, **Then** a transcript JSONL file, agent log, and usage JSON exist for that task.

4. **Given** a benchmark run encounters a task timeout, **When** the task completes, **Then** the task is marked as timed out in the summary and all partial artifacts are preserved.

5. **Given** a benchmark run encounters a model endpoint failure, **When** the task completes, **Then** the error is recorded in the summary and the run continues to the next task.

6. **Given** a completed benchmark run, **When** the summary file is inspected, **Then** it contains metadata including: model name, endpoint URL, hardware platform, total runtime, judge configuration, and per-task results.

7. **Given** a benchmark run is interrupted (e.g., by signal or crash), **When** the researcher inspects the output directory, **Then** completed task artifacts are preserved and a partial summary (or checkpoint) is available.

8. **Given** the benchmark run script is invoked, **When** it starts, **Then** it logs progress to stdout and a run-level log file, including task number, task ID, and status for each task.

### Edge Cases

- What happens when the local model endpoint becomes unreachable mid-run? The task times out, is recorded as failed, and the run continues after a configurable retry delay.
- What happens when a task requires tools not available in the TinyCUA harness (e.g., browser, email)? The task fails with a tool-availability error, which is recorded in the summary.
- What happens when the output disk fills up? The run pauses and logs an error; completed task artifacts are preserved.
- What happens when WildClawBench task data is missing or corrupted? The task is skipped with a clear error in the summary.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a benchmark runner script (e.g., `scripts/run_benchmark.py` or `scripts/run_benchmark.sh`) that iterates over all 60 WildClawBench tasks and invokes the TinyCUA harness for each.
- **FR-002**: The runner MUST invoke each task through the TinyCUA BaseAgent adapter (`TinyCUAAgent.run_task(spec)`) or equivalent CLI entry point.
- **FR-003**: The runner MUST produce a `summary_all.json` file containing aggregate results: per-task ID, score (if gradable), elapsed time, token usage, cost (zero for local models), and error status.
- **FR-004**: The runner MUST preserve per-task artifacts: transcript JSONL, agent log, and usage JSON in the task's output directory.
- **FR-005**: The runner MUST record benchmark metadata: local model name, endpoint URL, hardware platform (CPU/GPU/RAM), total wall-clock runtime, and judge configuration.
- **FR-006**: The runner MUST handle task timeouts gracefully — terminate the task, record timeout status, and continue to the next task.
- **FR-007**: The runner MUST handle model endpoint failures gracefully — record the error and continue.
- **FR-008**: The runner MUST log progress to stdout and a run-level log file.
- **FR-009**: The runner MUST support resuming from a checkpoint (skip already-completed tasks) in case of interruption.
- **FR-010**: The runner MUST NOT modify WildClawBench tasks or grading functions.
- **FR-011**: The runner MUST NOT depend on OpenRouter or any hosted model service.
- **FR-012**: The runner MUST use local model endpoint configuration (via environment variables or config file).

### Key Entities

- **Benchmark Runner**: Script that orchestrates the full 60-task execution, collecting results and artifacts.
- **Summary File (`summary_all.json`)**: Aggregate results file with per-task outcomes and metadata.
- **Per-Task Artifacts**: Transcript JSONL, agent log, usage JSON, and task output files for each of the 60 tasks.
- **Benchmark Metadata**: Model configuration, hardware info, runtime stats, and judge configuration.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **All 60 tasks executed**: Every WildClawBench task is attempted by the TinyCUA harness.
- [ ] **Summary file exists**: `summary_all.json` or equivalent is produced with per-task results.
- [ ] **Per-task artifacts preserved**: Each task has transcript, log, and usage artifacts in its output directory.
- [ ] **Timeout handling works**: Timed-out tasks are recorded as such and do not crash the run.
- [ ] **Endpoint failure handling works**: Model failures are recorded and the run continues.
- [ ] **Metadata recorded**: Model name, endpoint, hardware, runtime, and judge config are in the summary.
- [ ] **Resumability works**: If interrupted, the runner can skip completed tasks on restart.
- [ ] **Progress logging works**: Real-time progress is visible in stdout and a log file.
- [ ] **No OpenRouter dependency**: All model calls use local endpoints only.
- [ ] **Artifacts are analyzable**: A researcher can use the output to compare TinyCUA against other harnesses.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test summary file generation with mock task results.
- Test checkpoint/resume logic (skip completed tasks).
- Test timeout recording in summary.
- Test metadata collection (model, hardware, runtime).
- Test progress logging format.

### Integration Tests

- Test end-to-end run with a subset of tasks (e.g., 3 tasks from different categories).
- Test that `summary_all.json` is correctly populated after the run.
- Test that per-task artifacts exist and are valid.
- Test interruption and resume behavior.

### Manual Tests

- Run the full 60-task benchmark with a known local model (e.g., llama3 via vLLM).
- Verify `summary_all.json` contains all 60 task entries.
- Spot-check 5–10 task transcripts for correctness.
- Compare results against published WildClawBench baselines if available.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Benchmark runner script | TODO | scripts/run_benchmark.py or .sh |
| Summary file generation | TODO | summary_all.json output |
| Per-task artifact collection | TODO | Transcript, log, usage per task |
| Timeout handling | TODO | Graceful timeout + continue |
| Endpoint failure handling | TODO | Record error + continue |
| Metadata recording | TODO | Model, hardware, runtime, judge |
| Checkpoint/resume | TODO | Skip completed tasks on restart |
| Progress logging | TODO | stdout + log file |
| Unit tests | TODO | |
| Integration tests | TODO | |
| Full 60-task run | TODO | |

---

## Open Questions _(optional)_

1. **Should the benchmark runner use the CLI entry point or the Python API directly?**
   - **Owner**: @VJyzCELERY
   - **Status**: Open
   - **Proposed Answer**: Start with CLI entry point for consistency with smoke runs. If performance or control issues arise, switch to Python API.

2. **What local model should be used for the benchmark?**
   - **Owner**: @VJyzCELERY
   - **Status**: Open
   - **Proposed Answer**: Depends on available hardware. Document the model and configuration used in the summary metadata.

3. **Should concurrency be supported (multiple tasks in parallel)?**
   - **Owner**: @VJyzCELERY
   - **Status**: Open
   - **Proposed Answer**: Start with sequential execution for reproducibility. Add concurrency as a post-MVP optimization.

---

## Review Checklist

- [ ] No implementation details beyond what the design docs specify
- [ ] All mandatory sections completed
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
- [ ] Exit criteria match Milestone 5.6 from the roadmap issue
