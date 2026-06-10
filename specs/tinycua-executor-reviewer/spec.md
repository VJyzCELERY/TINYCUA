# Feature Specification: TaskExecutor and ResultReviewer Nodes

**Status**: Draft
**Created**: 2026-06-10
**Last Updated**: 2026-06-10
**Subproject(s) Affected**: tinycua (loops/task_executor, loops/result_reviewer, loops/tinycua_loop)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide `TinyCUATaskExecutorNode` and `TinyCUAResultReviewerNode` so the TinyCUA execution loop can **execute active tasks via ReAct-style processing and evaluate execution results with accept/retry/replan/open_question decisions**, completing the executor → reviewer → decision path that is the core execution loop of the architecture.
- **Gaps**: Milestone 3.1 delivered the Task/TaskResult/ReviewerDecision models and DFS active-task lifecycle helpers, but there are no concrete nodes that perform task execution or result review. The `AnalysisEffortNode._spawn_task_executor()` is a stub. The `WorkerNode._route_proceed_execution()` does not spawn TaskExecutor or ResultReviewer. The `_on_reviewer_retry/replan/open_question` methods on `TinyCUALoop` are no-op stubs. Without these nodes, the execution loop cannot actually run tasks or evaluate outcomes.
- **Non-Goals**: This spec does NOT cover ResultAggregationNode (Milestone 3.4), ResponseNode enhancements (Milestone 3.5), propagation/dedupe (Milestone 4.1), tool scoping (Milestone 4.2), or streaming (Milestone 4.4). It does NOT cover the `MandatoryPassthrough` routing for `open_question` (Milestone 3.3) — this spec only covers the reviewer emitting the `open_question` decision; the routing mechanism is deferred.
- **Constraints**: Must work without modifying `tinycua-sdk` public APIs. TaskExecutor must NOT mutate the active task or task tree — it receives a read-only snapshot and produces a `TaskResult`. ResultReviewer may update active task status/result but must NOT mutate task tree structure. The reviewer retry failure threshold (default 5) is distinct from `NodeRetryPolicy.max_attempts` and must be tracked at the loop or root-session level.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

After TaskAnalyzer and TaskAssessor have decomposed a task and AnalysisEffortNode has completed its planning passes, the execution loop needs to actually execute the active task and evaluate the result. TaskExecutor receives the active task from TinyCUALoop, executes it using available tools (ReAct-style), and produces a `TaskResult`. ResultReviewer then evaluates the execution result and decides: accept (task is done), retry (execution failed but plan is sound), replan (the plan itself needs revision), or open_question (need user clarification before proceeding).

### Acceptance Scenarios

1. **Given** an active task with `status="pending"`, **When** TaskExecutor is invoked, **Then** it executes the task using available tools and produces a `TaskResult` with `execution_status="succeeded"`.
2. **Given** TaskExecutor produces a `TaskResult`, **When** ResultReviewer evaluates it and the result satisfies the task's success criteria, **Then** the reviewer decides `accept` and the active task is marked done.
3. **Given** TaskExecutor produces a `TaskResult` with `execution_status="failed"`, **When** ResultReviewer evaluates it, **Then** the reviewer decides `retry` and the task remains active for re-execution.
4. **Given** ResultReviewer decides `retry` and the retry count reaches the failure threshold (default 5), **When** the reviewer evaluates again, **Then** it must either accept or escalate — no further retry is allowed.
5. **Given** ResultReviewer determines the task decomposition itself is flawed, **When** the reviewer decides `replan`, **Then** TaskAssessor and TaskAnalyzer (mode=local_replan) are spawned before TaskExecutor.
6. **Given** ResultReviewer needs user input to proceed, **When** the reviewer decides `open_question`, **Then** the ResultReviewer remains active with mandatory_passthrough targeting this ResultReviewer node.
7. **Given** ResultReviewer decides `accept` for the root task and all children are complete, **When** the loop processes the decision, **Then** the loop routes to ResultAggregationNode.
8. **Given** ResultReviewer decides `accept` for a non-root task, **When** the loop processes the decision, **Then** the loop recomputes the next active task and routes to TaskExecutor.
9. **Given** TaskExecutor needs additional context not available in the task, **When** it calls `enhanced_context_retrieval`, **Then** it receives relevant context and continues execution.
10. **Given** TaskExecutor is blocked and needs user input, **When** it emits a mandatory passthrough request, **Then** the user is prompted and the response is routed back to TaskExecutor.

### Edge Cases

- What happens when TaskExecutor is invoked but no active task exists? The node raises a `NodeExecutionError`.
- What happens when ResultReviewer receives a `TaskResult` with `execution_status="blocked"`? The reviewer should decide `open_question` or `retry` depending on the block reason.
- What happens when the retry failure threshold is reached and the reviewer still cannot accept? The reviewer must accept or escalate — it cannot retry again.
- What happens when replan spawns TaskAssessor + TaskAnalyzer but no unfinished tasks are selected? The system skips directly to TaskExecutor (no analyzer spawned per TaskAssessor contract).
- What happens when TaskExecutor's LLM call fails? The standard `NodeRetryPolicy` handles retry; if exhausted, `NodeExecutionError` is raised.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide `TinyCUATaskExecutorNode` as a concrete `ProcessNode`.
- **FR-002**: TaskExecutor MUST receive the active task reference from TinyCUALoop as input.
- **FR-003**: TaskExecutor MUST execute the active task using available tools in a ReAct-style loop (observe → think → act → observe).
- **FR-004**: TaskExecutor MUST produce a `TaskResult` with `task_id` matching the active task, `execution_status` reflecting the outcome, and a `summary` of what was done.
- **FR-005**: TaskExecutor MUST NOT mutate the active task or task tree structure — it receives a read-only snapshot.
- **FR-006**: TaskExecutor MAY use `enhanced_context_retrieval` to gather additional context during execution.
- **FR-007**: TaskExecutor MAY emit a mandatory passthrough / HITL request if blocked on user input.
- **FR-008**: On completion, TaskExecutor MUST advance the queue (next node is ResultReviewer).
- **FR-009**: System MUST provide `TinyCUAResultReviewerNode` as a concrete `ProcessNode`.
- **FR-010**: ResultReviewer MUST receive the TaskExecutor execution result as input.
- **FR-011**: ResultReviewer MUST decide one of: `accept`, `retry`, `replan`, `open_question`.
- **FR-012**: On `accept`, the system MUST update the active task status to `done` and recompute the next active task via DFS.
- **FR-013**: On `retry`, the system MUST preserve the same active task and advance to TaskExecutor for re-execution.
- **FR-014**: On `replan`, the system MUST spawn `TaskAssessor(scope=active_task_or_local_region)` and `TaskAnalyzer(mode=local_replan, init_enabled=false)` before TaskExecutor. Replan MUST NOT spawn `AnalysisEffortNode`.
- **FR-015**: On `open_question`, the system MUST keep ResultReviewer active and install mandatory_passthrough targeting this node/session.
- **FR-016**: The reviewer retry failure threshold MUST default to 5, be configurable, and be tracked at the loop or root-session level.
- **FR-017**: The retry failure counter MUST reset on a successful `accept`.
- **FR-018**: The retry failure threshold MUST be distinct from `NodeRetryPolicy.max_attempts`.
- **FR-019**: When the retry failure threshold is reached, the reviewer MUST accept or escalate — no further retry is permitted.
- **FR-020**: TaskExecutor node ID MUST be `"task_executor"` by default.
- **FR-021**: ResultReviewer node ID MUST be `"result_reviewer"` by default.
- **FR-022**: `AnalysisEffortNode._spawn_task_executor()` MUST be updated to actually spawn TaskExecutor and ResultReviewer (replacing the Milestone 3.1 stub).
- **FR-023**: `WorkerNode._route_proceed_execution()` MUST be updated to spawn TaskExecutor and ResultReviewer (replacing the Milestone 2.3 stub).
- **FR-024**: `TinyCUALoop._on_reviewer_retry()`, `_on_reviewer_replan()`, and `_on_reviewer_open_question()` MUST be updated from no-op stubs to real implementations.
- **FR-025**: System MUST NOT modify `tinycua-sdk` public APIs.

### Key Entities _(include if feature involves data)_

- **TaskExecutor**: A ProcessNode that executes the active task using tools and produces a TaskResult. Receives a read-only active task snapshot; must not mutate the task tree.
- **ResultReviewer**: A ProcessNode that evaluates TaskExecutor output and decides accept/retry/replan/open_question. Quality gate between execution and response. Tracks retry failure count.
- **ReviewerRetryState**: Tracks the retry failure count for the current active task. Reset on accept. Default threshold: 5. Stored at loop or root-session level.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **TaskExecutor executes active task**: Given an active task, TaskExecutor runs ReAct-style execution and produces a valid TaskResult.
- [ ] **ResultReviewer evaluates and decides**: Given a TaskResult, ResultReviewer decides accept/retry/replan/open_question.
- [ ] **Accept marks task done**: On accept, the active task status is set to done and DFS recomputes the next active task.
- [ ] **Retry preserves task**: On retry, the same task remains active and TaskExecutor is re-queued.
- [ ] **Replan spawns assessor+analyzer**: On replan, TaskAssessor and TaskAnalyzer (mode=local_replan) are spawned before TaskExecutor.
- [ ] **Open question keeps reviewer active**: On open_question, ResultReviewer remains active with mandatory_passthrough.
- [ ] **Retry threshold enforced**: After 5 retries (default), the reviewer cannot retry again — must accept or escalate.
- [ ] **Retry counter resets on accept**: After a successful accept, the retry counter resets to 0.
- [ ] **AnalysisEffortNode spawns executor**: `_spawn_task_executor()` creates TaskExecutor + ResultReviewer in the queue.
- [ ] **Worker proceed_execution spawns executor**: `_route_proceed_execution()` creates TaskExecutor + ResultReviewer in the queue.
- [ ] **Loop stubs implemented**: `_on_reviewer_retry/replan/open_question` are real implementations, not no-ops.
- [ ] **No SDK changes**: All implementation lives in `tinycua.loops` and `tinycua.models`.
- [ ] **Unit tests pass**: All new nodes and retry state logic have unit tests.
- [ ] **Integration tests pass**: End-to-end executor→reviewer path works with mocked LLM.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test `TinyCUATaskExecutorNode` construction with default node_id and config.
- Test `TinyCUATaskExecutorNode.__call__` with a mocked LLM that produces a successful execution result.
- Test `TinyCUATaskExecutorNode.__call__` raises `NodeExecutionError` when no active task is provided.
- Test `TinyCUATaskExecutorNode.on_complete` advances the queue.
- Test `TinyCUAResultReviewerNode` construction with default node_id and config.
- Test `TinyCUAResultReviewerNode.__call__` with mocked LLM producing accept decision.
- Test `TinyCUAResultReviewerNode.__call__` with mocked LLM producing retry decision.
- Test `TinyCUAResultReviewerNode.__call__` with mocked LLM producing replan decision.
- Test `TinyCUAResultReviewerNode.__call__` with mocked LLM producing open_question decision.
- Test `ReviewerRetryState` increment, reset, and threshold enforcement.
- Test `ReviewerRetryState` prevents retry when threshold reached.
- Test `_on_reviewer_retry` preserves active task and increments retry count.
- Test `_on_reviewer_replan` preserves active task and spawns assessor+analyzer.
- Test `_on_reviewer_open_question` preserves active task.
- Test `AnalysisEffortNode._spawn_task_executor` creates TaskExecutor + ResultReviewer in queue.
- Test `WorkerNode._route_proceed_execution` creates TaskExecutor + ResultReviewer in queue.

### Integration Tests

- Test full executor → reviewer → accept path with mocked LLM: active task is executed, reviewed, accepted, and next active task is selected.
- Test executor → reviewer → retry → executor path: retry increments counter, same task re-executed.
- Test executor → reviewer → replan → assessor → analyzer → executor path: replan spawns correct nodes.
- Test retry threshold enforcement: after 5 retries, reviewer accepts or escalates.
- Test root-task completion: accept on root task routes to aggregation-ready state.

### Manual Tests _(if applicable)_

- Run `create_tinycua_agent(...).run(...)` with a simple task and verify the executor → reviewer path completes.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| TinyCUATaskExecutorNode | TODO | ProcessNode for ReAct-style execution |
| TinyCUAResultReviewerNode | TODO | ProcessNode for result review |
| ReviewerRetryState | TODO | Retry failure counter with threshold |
| AnalysisEffortNode._spawn_task_executor | TODO | Replace stub with real spawning |
| WorkerNode._route_proceed_execution | TODO | Replace stub with real spawning |
| TinyCUALoop._on_reviewer_retry | TODO | Replace no-op with real impl |
| TinyCUALoop._on_reviewer_replan | TODO | Replace no-op with real impl |
| TinyCUALoop._on_reviewer_open_question | TODO | Replace no-op with real impl |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **Retry state storage location**: Should `ReviewerRetryState` be stored on `TinyCUALoop` or on `Session`?
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Proposed
   - **Proposed Answer**: Store on `TinyCUALoop` as `self._reviewer_retry_state: ReviewerRetryState`. The loop owns execution state; the session is a data container. This is consistent with `root_task` and `_active_task_id` being on the loop.

2. **TaskExecutor ReAct loop depth**: Should TaskExecutor have a maximum number of ReAct iterations per task?
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Proposed
   - **Proposed Answer**: Yes — use a configurable `max_react_iterations` (default 10) to prevent infinite tool-call loops. This is distinct from `NodeRetryPolicy.max_attempts` which controls LLM call retries.

---

## Review Checklist

- [ ] No implementation details — code, framework, or architecture choices must live in design docs only
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable

---

## References

- Design: `./design.md`
- Design docs:
  - `src/tinycua/docs/design/loops/task_executor.md` — TaskExecutor node architecture
  - `src/tinycua/docs/design/loops/result_reviewer.md` — ResultReviewer node architecture
  - `src/tinycua/docs/design/models/reviewer_decision.md` — ReviewerDecision model
  - `src/tinycua/docs/design/loops/tinycua_loop.md` — TinyCUALoop execution flow
- Existing specs:
  - `specs/tinycua-task-lifecycle/spec.md` — Task lifecycle models and helpers (completed, Milestone 3.1)
  - `specs/tinycua-task-analyzer/spec.md` — TaskAnalyzerNode (completed, Milestone 2.6)
- Issue: [#87](https://github.com/VJyzCELERY/TINYCUA/issues/87) — Milestone 3.2
