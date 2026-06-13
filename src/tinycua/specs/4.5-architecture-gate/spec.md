# Feature Specification: End-to-End TinyCUA Architecture Verification Gate

**Status**: Draft
**Created**: 2026-06-13
**Last Updated**: 2026-06-13
**Subproject(s) Affected**: tinycua (src/tinycua)
**Milestone**: 4.5 — End-to-End Architecture Verification Gate
**Tracking Issue**: [TBD]

> **Path convention**: All paths in this document (e.g., `docs/design/loops/node.md`, `config/node_config.py`) are relative to the `tinycua` subproject root (`src/tinycua/`). For example, `docs/design/loops/node.md` maps to `src/tinycua/docs/design/loops/node.md`.

---

## Problem Statement _(mandatory)_

- **Goals**: Verify that all 11 end-to-end architecture paths work correctly with a local LLM, establishing a verification gate that proves the complete TinyCUA agent orchestration is functional before proceeding to production hardening.
- **Gaps**: While individual components (QueryAnalyst, InformationDigester, Worker, TaskCreation, TaskExecutor, ResultReviewer, PrimaryAgent) have been implemented and tested in isolation, there is no comprehensive end-to-end verification that proves all 11 architecture paths work correctly with a real local LLM. Previous milestones tested components with mocked LLM responses; this milestone validates against actual LLM behavior.
- **Non-Goals**:
  - Modifying any source code, tests, or implementation files.
  - Implementing new features or fixing bugs discovered during verification.
  - Production deployment or performance optimization.
  - WildClawBench integration or benchmarking.
- **Constraints**:
  - Must use a local LLM endpoint (not cloud APIs) for reproducibility.
  - Must not modify existing source code — this is a verification-only milestone.
  - Gate pass/fail criteria must be objective and measurable.
  - Test infrastructure must be reusable for future regression testing.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer or CI system runs the architecture verification gate to confirm all 11 end-to-end paths work correctly with a local LLM. The gate produces a clear pass/fail verdict with detailed results for each path, enabling confident progression to the next milestone.

### Acceptance Scenarios

1. **Given** the verification gate is triggered, **When** all 11 paths complete successfully, **Then** the gate passes with a summary report showing all paths green.
2. **Given** the verification gate is triggered, **When** any path fails, **Then** the gate fails with a detailed report showing which path(s) failed, the error encountered, and the LLM response that caused the failure.
3. **Given** a path fails verification, **When** the developer investigates, **Then** the failure report includes the full LLM interaction log (messages sent, responses received) for debugging.
4. **Given** the verification gate runs, **When** it completes, **Then** results are persisted in a machine-readable format (JSON) for trend analysis and CI integration.
5. **Given** the verification gate runs against a local LLM, **When** the LLM is unavailable, **Then** the gate fails gracefully with a clear error message indicating the LLM endpoint is unreachable.

### Edge Cases

- What happens when the local LLM is slow but responsive? (Timeout configuration with generous defaults.)
- What happens when the LLM produces malformed output? (Retry logic should handle this; if not, the path fails and is reported.)
- What happens when a path takes longer than expected? (Per-path timeout with configurable limits.)
- What happens when the local LLM runs out of memory? (Gate fails with resource exhaustion error.)

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST define all 11 architecture paths with explicit node sequences and expected outcomes.
- **FR-002**: System MUST execute each path against a local LLM endpoint and verify the final output matches expected behavior.
- **FR-003**: System MUST produce a pass/fail verdict for each path with detailed success/failure information.
- **FR-004**: System MUST persist results in JSON format for machine consumption and CI integration.
- **FR-005**: System MUST provide configurable timeouts per path to handle slow LLM responses.
- **FR-006**: System MUST capture full LLM interaction logs for failed paths to enable debugging.
- **FR-007**: System MUST support running individual paths or the full suite.
- **FR-008**: System MUST produce a human-readable summary report alongside the JSON output.
- **FR-009**: System MUST validate that each node in the path executes and produces expected intermediate outputs.
- **FR-010**: System MUST verify session state is correctly propagated between nodes in each path.

### Key Entities

- **Architecture Path**: A named sequence of nodes (QueryAnalyst → InformationDigester → Worker → etc.) with expected inputs/outputs and final outcome.
- **Verification Gate**: The orchestrator that runs all paths and produces pass/fail verdicts.
- **Path Result**: The outcome of running a single path — pass/fail, duration, LLM interactions, error details.
- **Verification Report**: The aggregated results of all paths — overall pass/fail, per-path details, summary statistics.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **All 11 paths defined**: Each architecture path is explicitly defined with node sequence, expected inputs/outputs, and success criteria.
- [ ] **Verification gate runs**: The gate executes all 11 paths against a local LLM endpoint.
- [ ] **Gate passes when all paths succeed**: When all 11 paths complete successfully, the gate reports PASS.
- [ ] **Gate fails when any path fails**: When any path fails, the gate reports FAIL with detailed failure information.
- [ ] **Results persisted**: Verification results are saved in JSON format for machine consumption.
- [ ] **Human-readable report**: A summary report is generated showing per-path status and overall verdict.
- [ ] **LLM interaction logs**: Failed paths include full LLM interaction logs for debugging.
- [ ] **Configurable timeouts**: Per-path timeouts prevent indefinite hangs.
- [ ] **Individual path execution**: Paths can be run individually for targeted debugging.
- [ ] **No source code modifications**: All existing source code, tests, and implementation files remain unchanged.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Not applicable — this is a verification milestone, not an implementation milestone. No new code is written.

### Integration Tests

- Not applicable — the verification gate itself is the integration test.

### Manual Tests

- [ ] Run the verification gate against a local LLM and confirm all 11 paths pass.
- [ ] Verify the JSON output is well-formed and contains all expected fields.
- [ ] Verify the human-readable report is clear and actionable.
- [ ] Test failure reporting by temporarily misconfiguring a path.

---

## The 11 Architecture Paths

### Path 1: Passthrough (Simple)
- **Route**: QueryAnalyst → PrimaryAgent → Response
- **Description**: Simple query that goes directly to PrimaryAgent without digestion.
- **Expected Outcome**: PrimaryAgent produces a response without invoking InformationDigester.

### Path 2: Passthrough with Digestion
- **Route**: QueryAnalyst → PrimaryAgent → InformationDigester → PrimaryAgent → Response
- **Description**: Query classified as passthrough, but PrimaryAgent determines it needs consolidated context.
- **Expected Outcome**: PrimaryAgent invokes InformationDigester, receives digested information, produces response.

### Path 3: Worker (Simple)
- **Route**: QueryAnalyst → InformationDigester → Worker → TaskExecutor → ResultReviewer(accepted) → PrimaryAgent → Response
- **Description**: Simple worker path with single task execution.
- **Expected Outcome**: Worker processes single task, ResultReviewer accepts, PrimaryAgent produces response.

### Path 4: Worker with Task Creation
- **Route**: QueryAnalyst → InformationDigester → Worker → TaskCreation → TaskAssessor → TaskAnalyzer → TaskExecutor → ResultReviewer → PrimaryAgent → Response
- **Description**: Worker performs upfront task decomposition before execution.
- **Expected Outcome**: TaskCreation builds task tree, tasks executed sequentially, results aggregated.

### Path 5: Worker with Retry
- **Route**: QueryAnalyst → InformationDigester → Worker → TaskExecutor → ResultReviewer(retry) → TaskExecutor → ResultReviewer(accepted) → PrimaryAgent → Response
- **Description**: Task execution fails, ResultReviewer decides to retry.
- **Expected Outcome**: Task retried with failure context, second attempt succeeds.

### Path 6: Worker with Replan
- **Route**: QueryAnalyst → InformationDigester → Worker → TaskExecutor → ResultReviewer(replan) → TaskAnalyzer → TaskExecutor → ResultReviewer(accepted) → PrimaryAgent → Response
- **Description**: Task execution fails, ResultReviewer decides to replan by calling TaskAnalyzer.
- **Expected Outcome**: TaskAnalyzer decomposes current task, sub-tasks executed, results accepted.

### Path 7: Worker with Failure
- **Route**: QueryAnalyst → InformationDigester → Worker → TaskExecutor → ResultReviewer(failure) → HITL
- **Description**: Repeated failures reach threshold, Worker stays active for human-in-the-loop.
- **Expected Outcome**: Agent stays active with open question, ready for HITL interaction.

### Path 8: Worker with Task Decomposition
- **Route**: QueryAnalyst → InformationDigester → Worker → TaskCreation → TaskAssessor(decompose) → TaskAnalyzer → TaskExecutor → ResultReviewer → PrimaryAgent → Response
- **Description**: TaskAssessor identifies tasks needing decomposition during Task Creation.
- **Expected Outcome**: Complex tasks decomposed into sub-tasks, executed sequentially.

### Path 9: Worker with Task Recreation
- **Route**: QueryAnalyst → InformationDigester → Worker → TaskExecutor → ResultReviewer(recreation) → TaskCreation → TaskAssessor → TaskAnalyzer → TaskExecutor → ResultReviewer → PrimaryAgent → Response
- **Description**: ResultReviewer decides to recreate the task tree after execution.
- **Expected Outcome**: New task tree created, tasks executed, results aggregated.

### Path 10: Worker with Task Reanalysis
- **Route**: QueryAnalyst → InformationDigester → Worker → TaskExecutor → ResultReviewer(reanalysis) → TaskAnalyzer → TaskExecutor → ResultReviewer(accepted) → PrimaryAgent → Response
- **Description**: ResultReviewer decides to reanalyze the current task using TaskAnalyzer.
- **Expected Outcome**: TaskAnalyzer provides new decomposition, task re-executed, results accepted.

### Path 11: Worker with Proceed Execution
- **Route**: QueryAnalyst → InformationDigester → Worker → TaskExecutor → ResultReviewer(proceed) → TaskExecutor → ResultReviewer(accepted) → PrimaryAgent → Response
- **Description**: ResultReviewer decides to proceed with next task without special handling.
- **Expected Outcome**: Next task executed, results accepted, Worker completes.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Path definitions | TODO | Define all 11 paths with expected outcomes |
| Verification gate | TODO | Implement gate orchestrator |
| LLM integration | TODO | Configure local LLM endpoint |
| Result persistence | TODO | JSON output format |
| Human-readable report | TODO | Summary report generation |
| Timeout configuration | TODO | Per-path timeout limits |
| LLM interaction logging | TODO | Capture full logs for failed paths |

---

## Open Questions _(optional)_

1. **Which local LLM model should be used for verification?**
   - **Owner**: @VJyzCELERY
   - **Target**: TBD
   - **Status**: Discussion
   - **Proposed Answer**: Use a model that supports tool calling and has been validated in previous milestones.

2. **What are the pass/fail criteria for each path?**
   - **Owner**: @VJyzCELERY
   - **Target**: TBD
   - **Status**: Discussion
   - **Proposed Answer**: Each path must complete without exceptions and produce a non-empty response from PrimaryAgent.

3. **Should the gate run in CI or only locally?**
   - **Owner**: @VJyzCELERY
   - **Target**: TBD
   - **Status**: Discussion
   - **Proposed Answer**: Initially local-only, with CI integration as a follow-up milestone.

---

## Review Checklist

- [x] No implementation details beyond what the design docs specify
- [x] All mandatory sections completed
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
- [x] Exit criteria match Milestone 4.5 from the roadmap
