# Feature Specification: TinyCUAWorkerNode Optional LLM Decision

**Status**: Draft
**Created**: 2026-06-08
**Last Updated**: 2026-06-08
**Subproject(s) Affected**: tinycua (core)
**Milestone**: 2.3 — TinyCUAWorkerNode Optional LLM Decision
**Design**: ./design.md

---

## Problem Statement _(mandatory)_

- **Goals**: Provide optional LLM-based decision-making for TinyCUAWorkerNode so that when a task already exists, the worker can classify the appropriate next action (task_recreation, task_reanalysis, passthrough, proceed_execution) and dispatch to the correct route handler.
- **Gaps**: Milestone 2.2 established deterministic task-creation routing for WorkerNode, but when a task already exists, the worker has no concrete behavior beyond a stub that delegates to the parent DecisionNode. There are no route handlers for task_recreation, task_reanalysis, passthrough, or proceed_execution, and no dynamic classification label adjustment based on worker-spawned node presence.
- **Non-Goals**: Full downstream process-node implementations (Milestones 2.4–3.2), TaskAssessor, TaskExecutor, ResultReviewer, result aggregation, response synthesis, and full architecture verification (Milestone 4.5).
- **Constraints**: Must not modify tinycua-sdk public APIs. Must reuse existing DecisionNode, NodeQueue, TinyCUALoop, and RouteMap infrastructure. Must maintain QueryAnalyst queue invariant (first node). Worker must preserve original input query for downstream nodes. The two-step decision process (analysis → classification → dispatch) must follow the established DecisionNode pattern.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer creates a TinyCUA agent using `create_tinycua_agent(...)` and calls `.run("Help me write a script")`. QueryAnalyst classifies the input as `worker` and spawns a WorkerNode. WorkerNode enters, detects a task already exists, and performs the two-step LLM decision process: analysis call → classification call → validated RouteMap dispatch. Based on the classification label (task_recreation, task_reanalysis, passthrough, or proceed_execution), WorkerNode dispatches to the appropriate route handler.

### Acceptance Scenarios

1. **Given** a TinyCUA agent with WorkerNode active and a task exists, **When** WorkerNode enters, **Then** it performs the two-step LLM decision process (analysis → classification) without deterministic precheck bypass.
2. **Given** WorkerNode performs LLM classification and worker-spawned nodes exist, **When** classification returns a valid label, **Then** the `passthrough` label is included in the dynamic classification labels.
3. **Given** WorkerNode performs LLM classification and no worker-spawned nodes exist, **When** classification returns a valid label, **Then** the `passthrough` label is excluded from the dynamic classification labels.
4. **Given** WorkerNode classifies as `task_recreation`, **When** the route handler executes, **Then** it clears worker-spawned nodes and spawns TaskAnalyzerNode with TaskInit/TaskCreate tools (LLM-assisted).
5. **Given** WorkerNode classifies as `task_reanalysis`, **When** the route handler executes, **Then** it clears worker-spawned nodes and spawns TaskAnalyzerNode without TaskInit/TaskCreate tools.
6. **Given** WorkerNode classifies as `passthrough`, **When** the route handler executes, **Then** it calls `queue.advance()` and forwards input to the next worker-spawned node without re-inserting itself.
7. **Given** WorkerNode classifies as `proceed_execution`, **When** the route handler executes, **Then** it spawns or continues the TaskExecutor and ResultReviewer path.
8. **Given** WorkerNode receives an invalid or missing classification label, **When** the decision process completes, **Then** it retries according to NodeRetryPolicy.
9. **Given** WorkerNode's LLM classification returns the latest valid verdict, **When** multiple tool calls occur, **Then** the latest valid verdict determines the route label.
10. **Given** WorkerNode dispatches to any route handler, **When** the handler completes, **Then** it ensures the terminal response path exists.

### Edge Cases

- What happens when WorkerNode's LLM classification returns an invalid label? → **Design**: Retry per NodeRetryPolicy; if exhausted, raise NodeExecutionError. [§Error Handling](./design.md#error-handling)
- How does the system handle empty or null input reaching WorkerNode during LLM decision? → **Design**: WorkerNode passes through empty input; LLM decision process handles empty context gracefully. [§Error Handling](./design.md#error-handling)
- What is the behavior when passthrough is classified but no worker-spawned node exists? → **Design**: Dynamic label exclusion prevents passthrough from being offered; if somehow classified, route handler validates and retries. [§Error Handling](./design.md#error-handling)
- What happens when `clear_after_current()` in a route handler removes the terminal ResponseNode? → **Design**: Route handler MUST call `queue.ensure_terminal(default_response_node)` before returning. [§Error Handling](./design.md#error-handling)
- What happens when WorkerNode is re-entered and worker-spawned nodes are stale? → **Design**: Task_recreation or task_reanalysis routes clear stale nodes. [§Error Handling](./design.md#error-handling)

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide TinyCUAWorkerNode with LLM-based decision-making when a task exists.
- **FR-002**: WorkerNode MUST perform the two-step decision process: analysis LLM call → verdict/classification tool call → validated RouteMap dispatch.
- **FR-003**: WorkerNode MUST dynamically adjust classification labels based on worker-spawned node presence: include `passthrough` only when worker-spawned nodes exist.
- **FR-004**: WorkerNode MUST classify into one of: `task_recreation`, `task_reanalysis`, `passthrough`, `proceed_execution` (when task exists).
- **FR-005**: The latest valid classification result MUST determine the route label.
- **FR-006**: Invalid or missing classification labels MUST retry according to NodeRetryPolicy.
- **FR-007**: WorkerNode MUST provide route handlers for each worker route label.
- **FR-008**: The `task_recreation` route handler MUST clear worker-spawned nodes and spawn TaskAnalyzerNode with TaskInit/TaskCreate tools.
- **FR-009**: The `task_reanalysis` route handler MUST clear worker-spawned nodes and spawn TaskAnalyzerNode without TaskInit/TaskCreate tools.
- **FR-010**: The `passthrough` route handler MUST call `queue.advance()` and forward input to the next worker-spawned node without re-inserting WorkerNode.
- **FR-011**: The `proceed_execution` route handler MUST spawn or continue the TaskExecutor and ResultReviewer path.
- **FR-012**: Any route handler that calls `clear_after_current()` MUST call `queue.ensure_terminal(default_response_node)` before returning if the clear removed the terminal response path.
- **FR-013**: WorkerNode MUST preserve the original input query for downstream nodes.
- **FR-014**: WorkerNode MUST NOT use task creation, analysis, or execution tools (worker decision tools only).
- **FR-015**: QueryAnalyst MUST continue to handle worker spawn/reuse as defined in Milestone 2.1.
- **FR-016**: Queue invariant: QueryAnalyst is always the first node in the queue.

### Key Entities _(include if feature involves data)_

- **TinyCUAWorkerNode**: Concrete DecisionNode that owns task planning and execution orchestration. Replaces old worker subgraph and worker QueryAnalyst input gate.
- **WorkerRouteLabel**: Enum with labels: `task_creation`, `task_recreation`, `task_reanalysis`, `passthrough`, `proceed_execution`. All labels are implemented in this milestone.
- **WorkerOwnedQueueSegment**: The set of nodes spawned by WorkerNode, used for stale detection, clearing, and dynamic label adjustment.
- **RouteMap (Worker)**: WorkerNode's route map with labels mapped to handler callables. All five labels are registered in this milestone.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **SC-001** — **WorkerNode LLM decision process**: When a task exists, WorkerNode performs two-step LLM decision (analysis → classification) without deterministic precheck bypass.
- [ ] **SC-002** — **Dynamic label adjustment**: Classification labels include `passthrough` only when worker-spawned nodes exist.
- [ ] **SC-003** — **task_recreation route**: Route handler clears worker-spawned nodes and spawns TaskAnalyzerNode with TaskInit/TaskCreate tools.
- [ ] **SC-004** — **task_reanalysis route**: Route handler clears worker-spawned nodes and spawns TaskAnalyzerNode without TaskInit/TaskCreate tools.
- [ ] **SC-005** — **passthrough route**: Route handler advances queue and forwards input to next worker-spawned node.
- [ ] **SC-006** — **proceed_execution route**: Route handler spawns or continues TaskExecutor and ResultReviewer path.
- [ ] **SC-007** — **Invalid label retry**: Invalid or missing classification labels retry per NodeRetryPolicy.
- [ ] **SC-008** — **Terminal response path guarantee**: Route handlers calling `clear_after_current()` ensure terminal response path exists.
- [ ] **SC-009** — **Input preservation**: Original input query is preserved for downstream nodes.
- [ ] **SC-010** — **Queue invariant maintained**: QueryAnalyst remains first node in queue.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_worker_node_llm_decision_with_task`: WorkerNode performs two-step LLM decision when task exists.
- `test_worker_node_dynamic_labels_with_worker_spawned`: Classification labels include passthrough when worker-spawned nodes exist.
- `test_worker_node_dynamic_labels_without_worker_spawned`: Classification labels exclude passthrough when no worker-spawned nodes exist.
- `test_worker_node_classifies_task_recreation`: WorkerNode classifies as task_recreation.
- `test_worker_node_classifies_task_reanalysis`: WorkerNode classifies as task_reanalysis.
- `test_worker_node_classifies_passthrough`: WorkerNode classifies as passthrough.
- `test_worker_node_classifies_proceed_execution`: WorkerNode classifies as proceed_execution.
- `test_worker_node_invalid_label_retry`: Invalid classification labels trigger retry per NodeRetryPolicy.
- `test_worker_node_route_task_recreation`: task_recreation route handler clears and spawns correctly.
- `test_worker_node_route_task_reanalysis`: task_reanalysis route handler clears and spawns correctly.
- `test_worker_node_route_passthrough`: passthrough route handler advances queue correctly.
- `test_worker_node_route_proceed_execution`: proceed_execution route handler spawns executor/reviewer correctly.
- `test_worker_node_route_clear_ensures_terminal`: Route handlers ensure terminal response after clear.
- `test_worker_node_preserves_input`: Original input query is preserved.
- `test_worker_node_tool_scope`: WorkerNode only has access to worker decision tools.

### Integration Tests

- `test_worker_node_e2e_llm_decision`: End-to-end: QueryAnalyst → WorkerNode (LLM decision) → route handler → downstream nodes.
- `test_worker_node_e2e_task_recreation`: End-to-end: WorkerNode → task_recreation → TaskAnalyzerNode (+TaskInit/TaskCreate) → downstream.
- `test_worker_node_e2e_task_reanalysis`: End-to-end: WorkerNode → task_reanalysis → TaskAnalyzerNode (no TaskInit/TaskCreate) → downstream.
- `test_worker_node_e2e_passthrough`: End-to-end: WorkerNode → passthrough → next worker-spawned node.
- `test_worker_node_queue_shape_after_routes`: Queue shape after each route matches expected architecture.

### Manual Tests _(if applicable)_

- Verify WorkerNode LLM decision routing in a local environment with mock LLM endpoint.
- Verify dynamic label adjustment with and without worker-spawned nodes.
- Verify queue shape after each route visually.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| TinyCUAWorkerNode LLM decision | TODO | worker.py — two-step decision when task exists |
| Dynamic classification labels | TODO | Include/exclude passthrough based on worker-spawned nodes |
| task_recreation route handler | TODO | Clear + spawn TaskAnalyzerNode (+TaskInit/TaskCreate) |
| task_reanalysis route handler | TODO | Clear + spawn TaskAnalyzerNode (no TaskInit/TaskCreate) |
| passthrough route handler | TODO | Advance queue, forward input |
| proceed_execution route handler | TODO | Spawn TaskExecutor/ResultReviewer path |
| Invalid label retry | TODO | NodeRetryPolicy integration |
| Terminal response path guarantee | TODO | ensure_terminal() in all route handlers |

---

## Open Questions _(optional)_

1. **Should WorkerNode's LLM classification use a tool-call response format or free-text parsing?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Proposed
   - **Proposed Answer**: Use tool-call response format (function_call with WorkerRouteLabel enum) for structured, validated classification. This matches the established DecisionNode pattern from QueryAnalyst.

2. **What is the retry limit for invalid classification labels?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Proposed
   - **Proposed Answer**: Use NodeRetryPolicy with default max_retries=3, consistent with QueryAnalyst's retry behavior.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
