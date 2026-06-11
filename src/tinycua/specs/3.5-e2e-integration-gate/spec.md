# Feature Specification: End-to-End Integration Gate

**Status**: Draft
**Created**: 2026-06-12
**Last Updated**: 2026-06-12
**Subproject(s) Affected**: tinycua (loops, models, factory, config)
**Milestone**: 3.5 — E2E Integration Gate
**Design**: ./design.md

---

## Problem Statement _(mandatory)_

- **Goals**: Verify that the full TinyCUA architecture works end-to-end across all documented node paths, routing flows, and propagation behaviors — proving the prototype is ready for WildClawBench integration. Provide a single, repeatable verification entry point that exercises the complete `create_tinycua_agent(...).run(...)` flow with local LLM configuration.
- **Gaps**: Individual milestones (1.1–3.4) have been implemented and unit-tested in isolation, but no single verification pass confirms that all paths work together through the real queue execution loop. There is no documented contract for what "architecture complete" means, what paths must pass, or what artifacts are produced for failure analysis.
- **Non-Goals**: This spec does NOT cover WildClawBench adapter implementation (Milestone 5.x), Docker image creation, benchmark task execution, or production CLI/TUI UX. It does NOT implement new nodes, new routing logic, or new propagation rules — it verifies existing ones.
- **Constraints**: Must not modify `tinycua-sdk` public APIs. Must use the existing node set and queue infrastructure. Verification paths must use local LLM endpoints. All verification artifacts (logs, transcripts, task outputs) must be preserved for failure analysis.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer or CI pipeline runs a single command that exercises the complete TinyCUA architecture: the agent receives a user query, QueryAnalyst classifies it, a WorkerNode is spawned, tasks are created and analyzed, execution and review loops complete, results are aggregated, and a final response is produced — all through the real queue execution path with a local LLM endpoint.

### Acceptance Scenarios

1. **Given** a configured TinyCUA agent with local LLM endpoint, **When** `create_tinycua_agent(...).run("Help me with a simple task")` is called, **Then** the full architecture path executes without error and returns a final response string.
2. **Given** the agent is running with a simple task, **When** QueryAnalyst classifies the input, **Then** the passthrough, worker, and uncertain routes all produce deterministic, documented outcomes.
3. **Given** a task that triggers the worker path, **When** TaskCreate, TaskAnalyzer, and TaskAssessor nodes execute, **Then** a task tree is created and analyzed without queue corruption.
4. **Given** an active task with execution and review, **When** TaskExecutor runs and ResultReviewer decides, **Then** accept, retry, and replan routes all complete without deadlocking the queue.
5. **Given** a completed root task, **When** ResultAggregationNode traverses the task tree, **Then** an `AggregatedResult` is produced and passed to ResponseNode.
6. **Given** an `AggregatedResult`, **When** ResponseNode produces the final response, **Then** the output is a normalized string and the terminal node path is intact.
7. **Given** a context-insufficient scenario, **When** ResponseNode suspends for InformationDigester, **Then** the digester runs, produces a digest, and ResponseNode resumes to complete synthesis.
8. **Given** any node encounters a transient error, **When** retry is triggered, **Then** the retry policy is respected and the node either recovers or fails gracefully with a documented error state.
9. **Given** the verification gate runs, **When** all paths pass, **Then** a verification report artifact is produced with per-path pass/fail status and timing.
10. **Given** a path fails, **When** the gate completes, **Then** the failure is recorded with the failing node, session, input context, and error details for diagnosis.

### Edge Cases

- What happens when the local LLM endpoint is unreachable? The verification gate reports the path as failed with a connection error and does not hang indefinitely.
- What happens when a node exceeds its retry limit? The verification gate records the exhaustion as a failure for that path and continues testing remaining paths.
- What happens when the queue reaches a state where no node is active but the terminal ResponseNode has not been reached? The verification gate detects the queue stall and reports it.
- What happens when two verification paths share state (e.g., a session from path A is still active when path B starts)? The gate ensures path isolation or documents shared-state side effects.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a `verify_e2e_architecture()` entry point that runs all documented architecture paths sequentially and produces a verification report.
- **FR-002**: The verification gate MUST exercise the following paths: passthrough, worker task creation, task recreation/reanalysis, proceed execution, effort loop, executor/reviewer accept/retry/replan/open_question, aggregation, response, and response suspension/digestion.
- **FR-003**: Each path MUST be tested independently with a fresh agent instance or reset queue state to prevent cross-path contamination.
- **FR-004**: The gate MUST use local LLM endpoints (not hosted APIs) for all verification paths.
- **FR-005**: The gate MUST produce a verification report containing per-path pass/fail status, timing, node execution trace, and error details for failures.
- **FR-006**: The gate MUST set a configurable timeout per path and overall to prevent infinite hangs.
- **FR-007**: The gate MUST preserve all transcripts, logs, and task outputs for post-mortem analysis.
- **FR-008**: The gate MUST exit with a non-zero status code if any path fails, and zero only if all paths pass.
- **FR-009**: The gate MUST verify propagation/dedupe behavior (no duplicate session context entries) as part of the affected paths.
- **FR-010**: The gate MUST verify tool scoping (each node sees only allowed tools) as part of the affected paths.
- **FR-011**: The gate MUST verify retry and validation behavior (invalid output retries, exhaustion handling) as part of the affected paths.
- **FR-012**: The gate MUST verify streaming and transcript event behavior (stream=True and stream=False modes) for at least one path.
- **FR-013**: The gate MUST NOT modify `tinycua-sdk` public APIs.
- **FR-014**: The gate MUST be runnable via `uv run` from the tinycua subproject directory.

### Key Entities _(include if feature involves data)_

- **VerificationReport**: Aggregated result of all path verifications. Contains per-path results, overall pass/fail, timing, and artifact paths.
- **PathResult**: Individual path verification result. Contains path name, pass/fail status, execution time, node trace, error details (if any), and artifact references.
- **VerificationPath**: Named architecture path to verify (e.g., `passthrough`, `worker_task_creation`, `aggregation`, `response`). Each path maps to a specific node execution sequence.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **All architecture paths verified**: The gate exercises passthrough, worker task creation, task recreation/reanalysis, proceed execution, effort loop, executor/reviewer accept/retry/replan/open_question, aggregation, response, and response suspension/digestion paths.
- [ ] **Per-path isolation**: Each path runs with fresh state (agent instance or reset) to prevent cross-path contamination.
- [ ] **Local LLM only**: All verification paths use local LLM endpoints; no hosted API calls.
- [ ] **Verification report produced**: A structured report with per-path pass/fail, timing, and error details is generated.
- [ ] **Timeout enforcement**: Paths that exceed their timeout are terminated and reported as failures.
- [ ] **Artifact preservation**: Transcripts, logs, and task outputs are saved for all paths (pass and fail).
- [ ] **Exit code correct**: Non-zero if any path fails; zero only if all pass.
- [ ] **Propagation verified**: Duplicate session context entries are not produced across node transitions.
- [ ] **Tool scoping verified**: Each node sees only its allowed tool set.
- [ ] **Retry verified**: Invalid output triggers retry; exhaustion produces documented failure.
- [ ] **Streaming verified**: At least one path runs in stream=True mode and produces valid stream events.
- [ ] **No SDK changes**: All verification logic lives in `tinycua` subproject; no `tinycua-sdk` modifications.
- [ ] **Unit tests pass**: All new verification code has unit tests.
- [ ] **Integration tests pass**: End-to-end gate run succeeds against local LLM mock or endpoint.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test `VerificationReport` construction and serialization.
- Test `PathResult` construction with pass, fail, and timeout outcomes.
- Test per-path isolation (fresh agent instance or queue reset between paths).
- Test timeout enforcement (path exceeds timeout → terminated and reported).
- Test artifact path collection (transcripts, logs, task outputs referenced correctly).
- Test exit code logic (all pass → 0, any fail → non-zero).

### Integration Tests

- Test `verify_e2e_architecture()` runs all paths against a mock LLM endpoint and produces a passing report.
- Test that a failing path (e.g., mock LLM returns invalid output) produces a failing report with correct error details.
- Test that the gate terminates within overall timeout even if a path hangs.
- Test that streaming mode produces valid stream events for the streaming verification path.

### Manual Tests _(if applicable)_

- Run the gate against a real local LLM endpoint (e.g., vLLM or Ollama) and inspect the verification report.
- Verify artifact files (transcripts, logs) are complete and diagnosable for a failing path.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| `verify_e2e_architecture()` entry point | TODO | Core gate function |
| Path definitions (all 9 paths) | TODO | Maps path name to node execution sequence |
| Per-path agent instantiation | TODO | Fresh agent or queue reset per path |
| VerificationReport model | TODO | Structured output |
| PathResult model | TODO | Per-path result |
| Timeout enforcement | TODO | Per-path and overall |
| Artifact collection | TODO | Transcripts, logs, task outputs |
| Exit code logic | TODO | 0 = all pass, non-zero = any fail |
| Unit tests | TODO | Verification models and gate logic |
| Integration tests | TODO | Gate run against mock LLM |

---

## Open Questions _(optional)_

1. **Should the gate use a mock LLM or a real local endpoint for CI?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-12
   - **Status**: Discussion
   - **Proposed Answer**: Default to mock LLM for CI (deterministic, fast); support real local endpoint via environment variable for manual validation.

2. **How should path isolation be achieved — fresh agent instance per path, or queue reset?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-12
   - **Status**: Discussion
   - **Proposed Answer**: Fresh agent instance per path is simpler and guarantees isolation; queue reset is more efficient but risks residual state. Prefer fresh agent instance.

---

## Review Checklist

- [x] No implementation details — requirements describe WHAT, not HOW
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain (open questions are informational)
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
