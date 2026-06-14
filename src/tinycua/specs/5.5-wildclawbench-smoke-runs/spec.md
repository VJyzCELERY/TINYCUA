# Feature Specification: WildClawBench Smoke Runs

**Status**: Draft
**Created**: 2026-06-14
**Last Updated**: 2026-06-14
**Subproject(s) Affected**: tinycua
**Milestone**: 5.5 — WildClawBench Smoke Runs
**Tracking Issue**: https://github.com/VJyzCELERY/TINYCUA/issues/87

---

## Problem Statement _(mandatory)_

- **Goals**: Validate that the TinyCUA WildClawBench adapter, Docker image, CLI runtime, and artifact pipeline work end-to-end by running representative smoke tasks from each WildClawBench category, collecting scores/usage/logs/transcripts, and documenting failures.
- **Gaps**: Milestones 5.1–5.4 produced the individual components (CLI entry point, BaseAgent adapter, Docker image, transcript/usage artifacts), but no end-to-end smoke run has been executed to verify the full pipeline works against real WildClawBench tasks. There is no smoke-run orchestration script, no per-category task selection, and no structured failure documentation.
- **Non-Goals**:
  - Full 60-task benchmark run (Milestone 5.6).
  - Benchmark analysis report (Milestone 5.7).
  - Modifying WildClawBench tasks to make TinyCUA look better.
  - Production-quality CLI/TUI UX or HITL interrupt/resume.
  - Modifying `tinycua-sdk` public APIs.
- **Constraints**:
  - Must use the existing `create_tinycua_agent()` factory, `TinyCUALoop`, `TinyCUAAgent` adapter, and CLI without SDK API modifications.
  - Must use local OpenAI-compatible model endpoints for TinyCUA harness execution.
  - Judge LLM configuration is separate and managed outside this milestone.
  - Transcript, usage, and log artifacts MUST be compatible with WildClawBench grading (per Milestone 5.4).
  - Docker container MUST be able to reach the local model endpoint.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer runs the smoke-run script, which:
1. Selects at least one representative task from each WildClawBench category where dependencies are available.
2. For each selected task, builds the TinyCUA Docker image (if not cached), sets up the workspace, and runs the task via the WildClawBench adapter or CLI.
3. Collects scores, usage summaries, logs, transcripts, and task-output artifacts.
4. Produces a structured smoke-run report documenting pass/fail status per task, per-category results, and failure taxonomy.

### Acceptance Scenarios

1. **Given** the smoke-run script is invoked, **When** it completes, **Then** at least one task from each available WildClawBench category has been attempted.
2. **Given** a smoke-run task completes, **When** artifacts are collected, **Then** `agent.log`, `transcript.jsonl`, and `usage.json` exist in the task output directory.
3. **Given** a smoke-run task completes, **When** the transcript is inspected, **Then** it is OpenClaw-compatible JSONL parseable by WildClawBench's `transcript_loader.py`.
4. **Given** a smoke-run task completes, **When** usage is inspected, **Then** `usage.json` contains non-null token counts and request count.
5. **Given** a smoke-run task fails, **When** the failure is recorded, **Then** the failure category (harness crash, timeout, LLM error, missing dependency, grading error) is documented.
6. **Given** all smoke-run tasks complete, **When** the summary report is generated, **Then** it lists each task's category, status (pass/fail/skip), elapsed time, token usage, and failure reason (if any).
7. **Given** the smoke-run script is invoked, **When** a task's dependencies are unavailable (e.g., browser task without browser support), **Then** the task is skipped with a documented reason, not failed.

### Edge Cases

- What happens when the Docker image fails to build? The smoke run reports a build failure and skips all Docker-dependent tasks.
- What happens when the local model endpoint is unreachable? The smoke run reports a connection error and documents the endpoint configuration.
- What happens when a task exceeds the timeout? The task is marked as timeout with the configured limit recorded.
- What happens when grading fails on a completed task? The task is marked as "graded-error" with the grading error message.
- What happens when the workspace directory is not writable? The smoke run fails fast before any task execution.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a smoke-run orchestration script that selects representative tasks from each WildClawBench category.
- **FR-002**: Smoke-run task selection MUST include at least one task from each of the six WildClawBench categories: Productivity Flow, Code Intelligence, Social Interaction, Search & Retrieval, Creative Synthesis, Safety Alignment — where dependencies are available.
- **FR-003**: System MUST skip tasks whose dependencies are unavailable and document the skip reason, rather than failing them.
- **FR-004**: For each attempted task, System MUST collect: `agent.log`, `transcript.jsonl` (OpenClaw-compatible), `usage.json`, and task output files.
- **FR-005**: System MUST produce a structured smoke-run summary report (JSON or Markdown) listing per-task results: category, task ID, status (pass/fail/skip/timeout), elapsed time, token usage, and failure reason.
- **FR-006**: System MUST document failures by category: harness crash, timeout, LLM error, missing dependency, grading error, and other.
- **FR-007**: System MUST support configurable model endpoint (base URL, API key, model name) via environment variables or CLI flags.
- **FR-008**: System MUST support configurable timeout per task (default: 300 seconds).
- **FR-009**: System MUST NOT modify WildClawBench tasks to improve TinyCUA scores.
- **FR-010**: System MUST preserve all artifacts (logs, transcripts, usage, outputs) for post-run failure analysis.
- **FR-011**: System MUST support running smoke tasks both inside Docker (via adapter) and locally (via CLI `tinycua run`) for debugging.
- **FR-012**: Smoke-run script MUST be idempotent — re-running does not corrupt prior run artifacts.

### Key Entities _(include if feature involves data)_

- **SmokeTask**: A selected WildClawBench task for smoke execution — task ID, category, prompt, timeout, workspace path, output path.
- **SmokeResult**: Result of a single smoke task — task ID, category, status, elapsed time, usage summary, failure reason, artifact paths.
- **SmokeReport**: Aggregated results across all attempted tasks — per-task results, per-category summary, overall pass rate, failure taxonomy.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Smoke-run script exists**: An executable script that orchestrates smoke task execution.
- [ ] **All categories covered**: At least one task from each available WildClawBench category is attempted.
- [ ] **Artifacts collected**: Each attempted task produces `agent.log`, `transcript.jsonl`, and `usage.json`.
- [ ] **Transcript compatible**: `transcript.jsonl` from each task is parseable as OpenClaw-compatible JSONL.
- [ ] **Usage non-null**: `usage.json` from each task contains numeric token counts (never `null`).
- [ ] **Failures documented**: Failed tasks have categorized failure reasons in the summary report.
- [ ] **Skips documented**: Skipped tasks have documented skip reasons (missing dependencies).
- [ ] **Summary report generated**: A structured summary report exists listing all task results.
- [ ] **Idempotent re-runs**: Re-running the smoke script does not corrupt prior artifact directories.
- [ ] **Tests pass**: Unit and integration tests for smoke-run orchestration, task selection, and report generation.

---

## Testing Plan _(mandatory)_

### Unit Tests

- [ ] Test smoke-run task selection: correct category coverage, skip logic for missing dependencies.
- [ ] Test smoke result dataclass: construction, serialization, status enumeration.
- [ ] Test failure categorization: harness crash, timeout, LLM error, missing dependency, grading error.
- [ ] Test summary report generation: correct aggregation, per-category breakdown.
- [ ] Test idempotency: re-running does not overwrite prior artifact directories.

### Integration Tests

- [ ] Test end-to-end smoke run with a mock agent: task execution → artifact collection → report generation.
- [ ] Test Docker-based smoke run: Docker build → container start → task execution → artifact extraction.
- [ ] Test local CLI smoke run: `tinycua run` → artifact collection → report generation.

### Manual Tests _(if applicable)_

- [ ] Run smoke script against a live local model endpoint and verify artifacts are produced.
- [ ] Verify smoke-run report accurately reflects pass/fail/skip status for each task.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Smoke-run orchestration script | TODO | |
| Per-category task selection | TODO | |
| Failure categorization | TODO | |
| Summary report generation | TODO | |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **How should task selection work — static list or dynamic from WildClawBench dataset?**
   - **Owner**: @VJyzCELERY
   - **Target**: Before implementation
   - **Status**: Proposed
   - **Proposed Answer**: Start with a static curated list of representative tasks per category (one per category minimum). Dynamic selection from the dataset can be added later.

2. **Should smoke runs use Docker or local CLI by default?**
   - **Owner**: @VJyzCELERY
   - **Target**: Before implementation
   - **Status**: Proposed
   - **Proposed Answer**: Support both modes via a flag. Default to local CLI for faster iteration during development; Docker mode for validation runs.

---

## Review Checklist

- [x] No implementation details beyond what the design docs specify
- [x] All mandatory sections completed
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
- [x] Exit criteria match Milestone 5.5 from the roadmap issue
