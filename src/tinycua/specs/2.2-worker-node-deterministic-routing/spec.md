# Feature Specification: TinyCUAWorkerNode Deterministic Routing and TaskCreate

**Status**: Draft
**Created**: 2026-06-08
**Last Updated**: 2026-06-08
**Subproject(s) Affected**: tinycua (core)
**Milestone**: 2.2 — TinyCUAWorkerNode Deterministic Routing and TaskCreate
**Design**: ./design.md

---

## Problem Statement _(mandatory)_

- **Goals**: Provide deterministic task-creation routing for TinyCUAWorkerNode so that when no task exists, the worker can initialize task creation and analysis without requiring LLM decisions.
- **Gaps**: Milestone 2.1 established QueryAnalyst routing and worker spawn/reuse, but WorkerNode has no concrete behavior yet. There is no deterministic path for first-time task creation, no TaskCreateNode, and no worker-spawned-node detection or queue segment management.
- **Non-Goals**: Optional LLM worker decisions (Milestone 2.3), TaskAnalyzerNode full behavior (Milestone 2.4), TaskAssessorNode (Milestone 2.5), TaskExecutor (Milestone 3.2), result review, response synthesis, and full architecture verification (Milestone 4.5).
- **Constraints**: Must not modify tinycua-sdk public APIs. Must reuse existing DecisionNode, NodeQueue, TinyCUALoop, and RouteMap infrastructure. Must maintain QueryAnalyst queue invariant (first node). Worker must preserve original input query for downstream nodes.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer creates a TinyCUA agent using `create_tinycua_agent(...)` and calls `.run("Help me write a script")`. QueryAnalyst classifies the input as `worker` and spawns a WorkerNode. WorkerNode enters, detects no task exists, and deterministically routes to `task_creation`. TaskCreateNode creates the root task with TaskInit/TaskCreate tools, then TaskAnalyzerNode runs initial analysis without TaskInit/TaskCreate tools, followed by AnalysisEffortNode.

### Acceptance Scenarios

1. **Given** a TinyCUA agent with WorkerNode active and no task exists, **When** WorkerNode enters, **Then** it routes to `task_creation` deterministically without LLM decision.
2. **Given** WorkerNode enters with `task_creation` route, **When** TaskCreateNode completes and advances, **Then** the queue contains `[WorkerNode, TaskCreateNode, TaskAnalyzerNode, AnalysisEffortNode, TaskExecutor, ResultReviewer, ResponseNode]` (this is the expected queue shape AFTER TaskCreateNode completes and advances).
3. **Given** TaskCreateNode is active, **When** it creates the root task, **Then** it uses only TaskInit/TaskCreate tools and advances the queue.
4. **Given** TaskAnalyzerNode runs after TaskCreateNode, **When** it performs initial analysis, **Then** it does NOT have access to TaskInit/TaskCreate tools.
5. **Given** a WorkerNode already exists in the queue, **When** QueryAnalyst routes to worker, **Then** the existing WorkerNode is reused and counts as part of the worker-owned queue segment.
6. **Given** WorkerNode calls `clear_after_current()` in a route handler, **When** the clear removes the terminal response path, **Then** `queue.ensure_terminal(default_response_node)` is called before returning.
7. **Given** worker-spawned nodes exist in the queue, **When** WorkerNode is re-entered, **Then** it detects the worker-spawned segment for stale detection and clearing.

### Edge Cases

- What happens when TaskCreateNode fails to create the root task? → **Design**: Retry per NodeRetryPolicy; task creation failure prevents downstream nodes from receiving a valid task tree.
- How does the system handle an empty or null user input reaching WorkerNode? → **Design**: WorkerNode passes the original input through; downstream nodes handle empty input per their own policies.
- What is the behavior when WorkerNode is re-entered and worker-spawned nodes are stale? → **Design**: Deferred to Milestone 2.3 (LLM decision handles task_recreation/task_reanalysis).
- What happens when `clear_after_current()` removes the terminal ResponseNode? → **Design**: Route handler MUST call `queue.ensure_terminal(default_response_node)` before returning.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide TinyCUAWorkerNode as a concrete DecisionNode that owns task planning and execution orchestration.
- **FR-002**: WorkerNode MUST perform deterministic routing for `task_creation` when no task exists, without requiring LLM decision.
- **FR-003**: System MUST provide TinyCUATaskCreateNode as a concrete ProcessNode for deterministic root task creation.
- **FR-004**: TaskCreateNode MUST use only TaskInit/TaskCreate tools for root task creation.
- **FR-005**: TaskCreateNode MUST advance the queue after root task creation, with TaskAnalyzerNode as the next node.
- **FR-006**: TinyCUATaskAnalyzerNode (mode=initial_analysis) MUST run after TaskCreateNode without TaskInit/TaskCreate tools.
- **FR-007**: WorkerNode MUST detect worker-spawned nodes in the queue for stale detection and clearing.
- **FR-008**: WorkerNode MUST recognize an existing WorkerNode as part of the worker-owned queue segment for reuse.
- **FR-009**: Any route handler that calls `clear_after_current()` MUST call `queue.ensure_terminal(default_response_node)` before returning if the clear removed the terminal response path.
- **FR-010**: WorkerNode MUST preserve the original input query for downstream nodes.
- **FR-011**: WorkerNode MUST be a transient routing/continuation node that does not backward-propagate its own output directly.
- **FR-012**: WorkerNode MUST NOT use task creation, analysis, or execution tools (worker decision tools only).
- **FR-013**: QueryAnalyst MUST continue to handle worker spawn/reuse as defined in Milestone 2.1.
- **FR-014**: Queue invariant: QueryAnalyst is always the first node in the queue.

### Key Entities _(include if feature involves data)_

- **TinyCUAWorkerNode**: Concrete DecisionNode that owns task planning and execution orchestration. Replaces old worker subgraph and worker QueryAnalyst input gate.
- **TinyCUATaskCreateNode**: Concrete ProcessNode for deterministic first-time root task creation. Uses TaskInit/TaskCreate tools only.
- **WorkerOwnedQueueSegment**: The set of nodes spawned by WorkerNode, used for stale detection and clearing.
- **RouteMap (Worker)**: WorkerNode's route map with labels: `task_creation`, `task_recreation`, `task_reanalysis`, `passthrough`, `proceed_execution`. Only `task_creation` is deterministic in this milestone.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **WorkerNode deterministic task_creation routing**: When no task exists, WorkerNode routes to `task_creation` without LLM decision.
- [ ] **TaskCreateNode creates root task**: TaskCreateNode creates the root task using TaskInit/TaskCreate tools.
- [ ] **TaskAnalyzerNode runs after creation**: TaskAnalyzerNode (mode=initial_analysis) runs without TaskInit/TaskCreate tools.
- [ ] **Worker-spawned-node detection**: WorkerNode detects worker-spawned nodes for stale detection.
- [ ] **WorkerNode reuse**: Existing WorkerNode is recognized as part of worker-owned queue segment.
- [ ] **Terminal response path guarantee**: Route handlers calling `clear_after_current()` ensure terminal response path exists.
- [ ] **Input preservation**: Original input query is preserved for downstream nodes.
- [ ] **Queue invariant maintained**: QueryAnalyst remains first node in queue.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_worker_node_task_creation_route`: WorkerNode routes to `task_creation` when no task exists.
- `test_worker_node_deterministic_no_llm`: WorkerNode `task_creation` route does not trigger LLM decision.
- `test_task_create_node_creates_root_task`: TaskCreateNode creates root task with TaskInit/TaskCreate tools.
- `test_task_create_node_advances_queue`: TaskCreateNode advances queue after creation.
- `test_task_analyzer_no_task_tools`: TaskAnalyzerNode (initial_analysis) does not have TaskInit/TaskCreate tools.
- `test_worker_spawned_node_detection`: WorkerNode detects worker-spawned nodes in queue.
- `test_worker_node_reuse_detection`: Existing WorkerNode is recognized in worker-owned segment.
- `test_worker_node_preserves_input`: Original input query is preserved.
- `test_worker_node_tool_scope`: WorkerNode only has access to worker decision tools.
- `test_clear_after_current_ensures_terminal`: Route handler ensures terminal response after clear.

### Integration Tests

- `test_worker_node_e2e_task_creation`: End-to-end: QueryAnalyst → WorkerNode → TaskCreateNode → TaskAnalyzerNode → ResponseNode.
- `test_worker_node_task_creation_queue_shape`: Queue shape after `task_creation` route matches expected.
- `test_worker_node_reuse_with_task_creation`: QueryAnalyst reuses existing WorkerNode, WorkerNode routes to `task_creation`.

### Manual Tests _(if applicable)_

- Verify WorkerNode deterministic routing in a local environment with mock LLM endpoint.
- Verify queue shape after `task_creation` route visually.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| TinyCUAWorkerNode | TODO | Concrete DecisionNode with route_map |
| TinyCUATaskCreateNode | TODO | ProcessNode for root task creation |
| Worker-spawned-node detection | TODO | Detection and segment management |
| WorkerNode reuse detection | TODO | Existing WorkerNode in queue segment |
| Terminal response path guarantee | TODO | ensure_terminal in route handlers |
| Input preservation | TODO | Original query passthrough |

---

## Open Questions _(optional)_

1. **Should TaskCreateNode have its own retry policy or inherit from WorkerNode?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Discussion
   - **Proposed Answer**: TaskCreateNode should have its own NodeRetryPolicy config, independent of WorkerNode.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
