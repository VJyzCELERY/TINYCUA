# Feature Specification: End-to-End TinyCUA Architecture Verification Gate

**Status**: Draft
**Created**: 2026-06-13
**Last Updated**: 2026-06-13
**Subproject(s) Affected**: tinycua (src/tinycua)
**Milestone**: 4.5 — End-to-End TinyCUA Architecture Verification Gate
**Tracking Issue**: https://github.com/VJyzCELERY/TINYCUA/issues/87

> **Path convention**: All paths in this document (e.g., `docs/design/loops/node.md`, `config/node_config.py`) are relative to the `tinycua` subproject root (`src/tinycua/`). For example, `docs/design/loops/node.md` maps to `src/tinycua/docs/design/loops/node.md`.

---

## Problem Statement _(mandatory)_

- **Goals**: Verify that the complete TinyCUA target architecture works end-to-end across all documented paths before proceeding to WildClawBench integration. This is a **gate** — WildClawBench work must not begin until this gate passes.
- **Gaps**: Prior milestones (1.1–4.4) implemented individual components (agent factory, session config, nodes, queue, routing, propagation, retry/validation, streaming). However, there is no consolidated verification that all components work together across every documented architecture path with a local LLM endpoint.
- **Non-Goals**:
  - Implementing new features or nodes (all components should exist from prior milestones).
  - WildClawBench adapter or Docker integration ( Milestone 5).
  - Performance optimization or production hardening.
  - Modifying `tinycua-sdk` public APIs.
- **Constraints**:
  - Must use local LLM model endpoint for all verification runs.
  - Must not modify existing node/loop/queue contracts.
  - Verification must cover every path documented in `docs/design/loops/expected_scenarios.md`.
  - Exit criteria must be met before the gate passes.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer or CI pipeline runs `create_tinycua_agent(...).run(query)` with a local LLM endpoint. The agent processes the query through the full TinyCUA node flow — QueryAnalyst → InformationDigester → Worker → TaskCreate/TaskAnalyzer → AnalysisEffort → TaskExecutor → ResultReviewer → ResultAggregation → ResponseNode — and produces a valid final response. This works for every documented architecture path.

### Acceptance Scenarios

1. **Given** a new user query with no existing task, **When** `create_tinycua_agent(...).run(query)` is called, **Then** the agent creates a root task, executes it, reviews results, aggregates, and returns a final response (passthrough/first-time task creation path).

2. **Given** an existing task with no active executor, **When** a follow-up query is processed, **Then** the Worker chooses `proceed_execution` and the TaskExecutor completes the next active task (proceed execution path).

3. **Given** an existing task that needs re-evaluation, **When** the Worker determines recreation or reanalysis is needed, **Then** the TaskAnalyzer runs in the appropriate mode and the task tree is updated (task recreation/reanalysis path).

4. **Given** a task with non-zero effort level (low/medium/high), **When** AnalysisEffortNode runs, **Then** TaskAssessor and TaskAnalyzer are prepended for the configured number of passes before TaskExecutor is spawned (effort loop path).

5. **Given** a task execution that fails validation, **When** ResultReviewer retries, **Then** the executor/reviewer path handles accept/retry/replan/open_question correctly with the retry failure threshold (executor/reviewer path).

6. **Given** an accepted root task, **When** ResultAggregation runs, **Then** it performs guided BFS right-to-left traversal and produces response-ready context (aggregation path).

7. **Given** aggregated context, **When** ResponseNode runs, **Then** it synthesizes a final response as a string (response path).

8. **Given** a ResponseNode that needs additional context, **When** it suspends to InformationDigester, **Then** the digester runs in a fresh session, produces a digest, and the ResponseNode resumes synthesis (response suspension/digestion path).

9. **Given** a Worker that needs context before task operations, **When** QueryAnalyst spawns InformationDigester before Worker, **Then** the digester produces a digest that propagates to the Worker's session context (worker suspension/digestion path).

10. **Given** nodes propagating context, **When** multiple nodes execute, **Then** propagation/dedupe works correctly, tool scoping restricts each node to its allowed tools, retry/validation catches invalid output, and streaming emits structured events when enabled (propagation/dedupe/tool scoping/retry/streaming path).

### Edge Cases

- What happens when the local LLM endpoint is unavailable? (Verification should document the error behavior.)
- What happens when a node exhausts retries during verification? (Failure state should be recorded and propagated correctly.)
- What happens when the task tree has multiple nested tasks? (Active task selection via DFS pre-order should work correctly.)
- What happens when streaming is enabled during verification? (Lifecycle events should be emitted and serializable.)

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST successfully execute `create_tinycua_agent(...).run(query)` across all documented architecture paths using a local LLM endpoint.
- **FR-002**: System MUST verify the passthrough path (simple query → QueryAnalyst → Worker → ResponseNode).
- **FR-003**: System MUST verify the worker task creation path (new query → QueryAnalyst → InformationDigester → Worker → TaskCreate → TaskAnalyzer → AnalysisEffort → TaskExecutor → ResultReviewer → ResultAggregation → ResponseNode).
- **FR-004**: System MUST verify the task recreation/reanalysis path (Worker determines task needs re-evaluation → TaskAnalyzer in recreation/reanalysis mode).
- **FR-005**: System MUST verify the proceed execution path (existing task → Worker → TaskExecutor → ResultReviewer → ResultAggregation → ResponseNode).
- **FR-006**: System MUST verify the effort loop path (AnalysisEffortNode with non-zero effort → TaskAssessor + TaskAnalyzer prepended for configured passes → TaskExecutor).
- **FR-007**: System MUST verify the executor/reviewer accept/retry/replan/open_question path (TaskExecutor fails validation → ResultReviewer retries → accept, replan, or open_question routing).
- **FR-008**: System MUST verify the aggregation path (accepted root task → ResultAggregation guided BFS → response-ready context).
- **FR-009**: System MUST verify the response path (aggregated context → ResponseNode → final string response).
- **FR-010**: System MUST verify the response suspension/digestion path (ResponseNode suspends → InformationDigester runs in fresh session → digest propagates back → ResponseNode resumes).
- **FR-011**: System MUST verify the worker suspension/digestion path (QueryAnalyst spawns InformationDigester before Worker → digest propagates to Worker session context).
- **FR-012**: System MUST verify propagation/dedupe works correctly across node executions.
- **FR-013**: System MUST verify tool scoping restricts each node to its allowed tools.
- **FR-014**: System MUST verify retry/validation catches invalid output and retries with assistant-role continuations.
- **FR-015**: System MUST verify streaming emits structured lifecycle events when `stream=True`.
- **FR-016**: System MUST produce a verification report documenting pass/fail status for each architecture path.
- **FR-017**: All verification tests MUST use a local LLM model endpoint (not cloud APIs).

### Key Entities _(include if feature involves data)_

- **Verification Report**: A structured document recording pass/fail status, logs, and any issues found for each architecture path.
- **Architecture Path**: A documented end-to-end flow from `docs/design/loops/expected_scenarios.md` that must be verified.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

> **Note**: Items below are checked off as verification progresses. All items must
> be checked before the gate passes.

- [ ] **Passthrough path works**: Simple query → QueryAnalyst → passthrough → Worker → ResponseNode produces valid response.
- [ ] **Task creation path works**: New query → QueryAnalyst → InformationDigester → Worker → TaskCreate → TaskAnalyzer → AnalysisEffort → TaskExecutor → ResultReviewer → ResultAggregation → ResponseNode produces valid response.
- [ ] **Task recreation/reanalysis works**: Worker determines task needs re-evaluation → TaskAnalyzer runs in appropriate mode → task tree updated.
- [ ] **Proceed execution works**: Existing task → Worker → TaskExecutor → ResultReviewer → ResultAggregation → ResponseNode completes without re-creating task.
- [ ] **Effort loop works**: AnalysisEffortNode with non-zero effort prepends TaskAssessor + TaskAnalyzer for configured passes before spawning TaskExecutor.
- [ ] **Executor/reviewer accept works**: TaskExecutor completes task → ResultReviewer accepts → advances to aggregation.
- [ ] **Executor/reviewer retry works**: TaskExecutor produces invalid output → ResultReviewer retries → eventually accepts or exhausts.
- [ ] **Executor/reviewer replan works**: TaskExecutor cannot complete → ResultReviewer triggers local replan → TaskAnalyzer re-evaluates task.
- [ ] **Executor/reviewer open_question works**: TaskExecutor requests user input → ResultReviewer routes to open_question → flow handles continuation.
- [ ] **Aggregation works**: Accepted root task → ResultAggregation guided BFS → response-ready context produced.
- [ ] **Response works**: Aggregated context → ResponseNode → final string response returned.
- [ ] **Response suspension/digestion works**: ResponseNode suspends → InformationDigester runs → digest propagates back → ResponseNode resumes and produces response.
- [ ] **Worker suspension/digestion works**: QueryAnalyst spawns InformationDigester before Worker → digest propagates to Worker session context → Worker receives digested context.
- [ ] **Propagation/dedupe works**: Node context propagates without duplicate reusable session context.
- [ ] **Tool scoping works**: Each node sees only its allowed tools.
- [ ] **Retry/validation works**: Invalid node output triggers retry with assistant-role continuation.
- [ ] **Streaming works**: `stream=True` emits structured lifecycle events serializable to JSONL.
- [ ] **Local LLM endpoint used**: All verification runs use a local model endpoint (not cloud APIs).
- [ ] **Verification report produced**: Pass/fail status documented for each architecture path.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Verify each node type can be instantiated and called individually with mock LLM responses.
- Verify NodeQueue execution, advance(), suspend_current_and_prepend(), and ensure_terminal().
- Verify propagation rules and dedupe logic.
- Verify tool policy resolution for each node type.
- Verify retry/validation loop behavior.
- Verify streaming event emission.

### Integration Tests

- End-to-end test: `create_tinycua_agent(...).run(query)` with a local LLM endpoint through each documented architecture path.
- Multi-node queue execution test: QueryAnalyst → Worker → TaskExecutor → ResultReviewer → ResponseNode.
- Suspension/digestion test: ResponseNode suspension to InformationDigester and resume.
- Worker digestion test: QueryAnalyst → InformationDigester → Worker with digest propagation.
- Effort loop test: AnalysisEffortNode with medium effort → TaskAssessor + TaskAnalyzer × 2 passes → TaskExecutor.

### Manual Tests _(if applicable)_

- Run `create_tinycua_agent(...).run("Fix the login bug")` with a local LLM and observe the full node flow.
- Verify streaming events are emitted correctly with `stream=True`.
- Verify the verification report is complete and accurate.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Verification test suite | TODO | Create test cases for each architecture path |
| Local LLM endpoint setup | TODO | Configure local model for verification |
| Passthrough path verification | TODO | |
| Task creation path verification | TODO | |
| Task recreation/reanalysis verification | TODO | |
| Proceed execution verification | TODO | |
| Effort loop verification | TODO | |
| Executor/reviewer path verification | TODO | |
| Aggregation path verification | TODO | |
| Response path verification | TODO | |
| Suspension/digestion verification | TODO | |
| Propagation/dedupe verification | TODO | |
| Tool scoping verification | TODO | |
| Retry/validation verification | TODO | |
| Streaming verification | TODO | |
| Verification report generation | TODO | |

---

## Open Questions _(optional)_

1. **What local LLM model should be used for verification?**
   - **Owner**: @VJyzCELERY
   - **Status**: Open
   - **Proposed Answer**: Use the smallest model that can follow tool-call instructions (e.g., a fine-tuned Qwen or Llama variant). Document model name, endpoint, and hardware in the verification report.

2. **Should verification tests be automated in CI or manual?**
   - **Owner**: @VJyzCELERY
   - **Status**: Open
   - **Proposed Answer**: Both — automated integration tests for the core paths, manual verification for edge cases and streaming behavior.

---

## Review Checklist

- [x] No implementation details beyond what the design docs specify
- [x] All mandatory sections completed
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
- [x] Exit criteria match Milestone 4.5 from the roadmap issue
