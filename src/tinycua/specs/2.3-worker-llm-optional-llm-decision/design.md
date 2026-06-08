# Design Document: TinyCUAWorkerNode Optional LLM Decision

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-08

---

## Overview

This design implements optional LLM-based decision-making for TinyCUAWorkerNode. When a task already exists, WorkerNode performs the two-step DecisionNode process (analysis LLM call → classification tool call → validated RouteMap dispatch) to classify the appropriate next action. The four remaining route labels (task_recreation, task_reanalysis, passthrough, proceed_execution) are implemented with their corresponding route handlers. Dynamic classification label adjustment is introduced to include `passthrough` only when worker-spawned nodes exist.

---

## Architecture

### Component Overview

```
[QueryAnalyst] --> [WorkerNode] --> [Route Handler] --> [Downstream Nodes]
                     |                  |
                     ├── LLM Decision   ├── task_recreation → TaskAnalyzerNode(+TaskInit/TaskCreate)
                     │   (analysis →    ├── task_reanalysis → TaskAnalyzerNode(no TaskInit/TaskCreate)
                     │    classify)     ├── passthrough → advance queue, forward to next worker-spawned node
                     │                  └── proceed_execution → log + ensure_terminal (TaskExecutor/ResultReviewer deferred to 3.2)
                     ├── Dynamic Labels
                     │   (passthrough only when worker-spawned nodes exist)
                     └── NodeRetryPolicy (invalid labels)
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops.worker.TinyCUAWorkerNode` | Modified | Add LLM decision process when task exists, dynamic label adjustment, route handlers |
| `tinycua.loops.worker.WorkerRouteLabel` | Modified | Add four new route labels (task_recreation, task_reanalysis, passthrough, proceed_execution); task_creation already exists from Milestone 2.2 |
| `tinycua.loops.worker._build_default_route_map()` | Modified | Register all five route labels in the default RouteMap |

---

## Data Model

### Modified Entities

```python
from enum import Enum

# WorkerNode route labels — all five labels implemented in this milestone
class WorkerRouteLabel(str, Enum):
    task_creation = "task_creation"            # Deterministic, no LLM (Milestone 2.2)
    task_recreation = "task_recreation"        # LLM-assisted, clear + spawn TaskAnalyzerNode(+TaskInit/TaskCreate)
    task_reanalysis = "task_reanalysis"        # LLM-assisted, clear + spawn TaskAnalyzerNode(no TaskInit/TaskCreate)
    passthrough = "passthrough"                # LLM-assisted, advance queue, forward input
    proceed_execution = "proceed_execution"    # LLM-assisted, terminal route (log + ensure_terminal); TaskExecutor/ResultReviewer deferred to 3.2
```

### WorkerOwnedQueueSegment

The set of nodes spawned by WorkerNode, used for stale detection, clearing, and dynamic label adjustment.

```python
# WorkerOwnedQueueSegment: nodes spawned by WorkerNode
# Detection: queue.find_worker_spawned_nodes()
# Clearing: queue.clear_after_current() removes worker-spawned nodes
# The segment is used for:
#   - Stale detection (are spawned nodes still valid?)
#   - Dynamic label adjustment (include passthrough only when segment is non-empty)
```

**Detection**: `queue.find_worker_spawned_nodes()` returns all nodes spawned by WorkerNode after itself in the queue.

**Clearing**: `queue.clear_after_current()` removes worker-spawned nodes from the queue.

**Dynamic label adjustment**: The segment determines whether `passthrough` is a valid classification option — it is only offered when the segment is non-empty.

### Current State

The existing WorkerNode uses a static tuple of all WorkerRouteLabel values:

```python
# In worker.py:33
_DEFAULT_WORKER_LABELS: tuple[str, ...] = tuple(label.value for label in WorkerRouteLabel)
```

This constant is used in `__init__()` to set `classification_labels`:

```python
# In worker.py:70
classification_labels=list(_DEFAULT_WORKER_LABELS),  # tuple → list for parent
```

**Limitation**: The static approach includes all labels regardless of queue state. This means `passthrough` is offered as a classification option even when no worker-spawned node exists to receive it, leading to potential invalid routing.

### Dynamic Label Adjustment

```python
def _get_classification_labels(self, queue: NodeQueue) -> list[str]:
    """Get classification labels based on current worker-spawned node state.
    
    Args:
        queue: The node queue to check for worker-spawned nodes.
    
    Returns:
        List of valid classification labels. Includes 'passthrough' only when
        worker-spawned nodes exist in the queue.
    
    Note: task_creation is excluded because it is handled by deterministic
    precheck before LLM decision (Milestone 2.2). The precheck in __call__()
    routes to task_creation directly when no task exists, so it never reaches
    the LLM classification step.
    """
    labels = [
        WorkerRouteLabel.task_recreation.value,
        WorkerRouteLabel.task_reanalysis.value,
        WorkerRouteLabel.proceed_execution.value,
    ]
    if self._has_worker_spawned_nodes(queue):
        labels.append(WorkerRouteLabel.passthrough.value)
    return labels
```

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
class TinyCUAWorkerNode(DecisionNode):
    """
    Concrete DecisionNode that owns task planning and execution orchestration.
    Replaces old worker subgraph and worker QueryAnalyst input gate.
    """
    
    route_map: RouteMap  # Maps route labels to handler callables
    
    def __call__(self, input: NodeInputLike) -> DecisionResult:
        """
        WorkerNode entry point. Performs deterministic precheck before LLM decision.
        When no task exists, routes to task_creation deterministically (Milestone 2.2).
        When a task exists, delegates to standard LLM decision flow (Milestone 2.3).
        """
    
    def _detect_task_exists(self) -> bool:
        """Check if a task already exists in the session via self.session.task."""
    
    def _has_worker_spawned_nodes(self, queue: NodeQueue) -> bool:
        """Check if worker-spawned nodes exist in the queue.
        
        New method added in Milestone 2.3. Convenience wrapper around the existing
        _detect_worker_spawned_nodes(queue) method (which returns a list). This
        method returns a bool for use in dynamic label adjustment and other boolean
        checks.
        
        Args:
            queue: The node queue to search for worker-spawned nodes.
        """
    
    def _get_classification_labels(self, queue: NodeQueue) -> list[str]:
        """Get dynamic classification labels based on worker-spawned node presence.
        
        Returns a list of valid classification labels. Caller should use the
        returned list for classification.
        
        Args:
            queue: The node queue to check for worker-spawned nodes.
        """
    
    def _route_task_creation(self, queue: NodeQueue, result: DecisionResult) -> None:
        """Deterministic route: spawn TaskCreateNode then TaskAnalyzerNode."""
    
    def _route_task_recreation(self, queue: NodeQueue, result: DecisionResult) -> None:
        """LLM-assisted route: clear worker-spawned nodes, spawn TaskAnalyzerNode(+TaskInit/TaskCreate).
        
        Note: Unlike task_creation (which spawns TaskCreateNode + TaskAnalyzerNode),
        task_recreation only spawns TaskAnalyzerNode with mode="analysis" (which
        includes TaskInit/TaskCreate in its tool_scope). This is because the task
        already exists and doesn't need to be recreated from scratch.
        """
    
    def _route_task_reanalysis(self, queue: NodeQueue, result: DecisionResult) -> None:
        """LLM-assisted route: clear worker-spawned nodes, spawn TaskAnalyzerNode(no TaskInit/TaskCreate)."""
    
    def _route_passthrough(self, queue: NodeQueue, result: DecisionResult) -> None:
        """LLM-assisted route: advance queue, forward input to next worker-spawned node.
        
        Defensive validation: Checks that worker-spawned nodes exist before advancing.
        If no worker-spawned node exists, raises NodeExecutionError (should not happen
        since dynamic labels exclude passthrough when no spawned nodes exist).
        
        Input forwarding: Calls queue.advance() to remove WorkerNode, then calls
        queue.set_input(next_node, self._last_input) to forward the original input
        to the next worker-spawned node. Uses self._last_input (see Input Preservation
        section for details).
        """
    
    def _route_proceed_execution(self, queue: NodeQueue, result: DecisionResult) -> None:
        """LLM-assisted route: log classification and ensure terminal response.

        Milestone 2.3: Logs the classification and ensures the terminal response
        path exists. TaskExecutor/ResultReviewer spawning is deferred to Milestone 3.2
        (Phase 2). This handler acts as a terminal route for Milestone 2.3 — the
        queue reaches a stable state with the default response node.
        """
```

### Route Handler Terminal Node

Route handlers that clear the queue must ensure a terminal response path. The `default_response_node` parameter passed to `queue.ensure_terminal()` is a class attribute on WorkerNode that provides the fallback terminal node.

```python
class TinyCUAWorkerNode(DecisionNode):
    # ... existing code ...
    
    default_response_node: Node  # Terminal node for ensure_terminal() calls
```

**Usage in route handlers**:
```python
def _route_task_recreation(self, queue: NodeQueue, result: DecisionResult) -> None:
    queue.clear_after_current()
    # Spawn TaskAnalyzerNode...
    queue.ensure_terminal(self.default_response_node)
```

**Origin**: This follows the pattern established in Milestone 2.2 (deterministic routing) where route handlers ensure terminal response paths. The `default_response_node` is set during WorkerNode initialization and referenced by all route handlers that modify the queue.

### Two-Step Decision Process

The two-step decision process follows the established DecisionNode pattern from QueryAnalyst:

1. **Analysis LLM call**: WorkerNode sends the current session state and worker context to the LLM for analysis.
2. **Classification tool call**: WorkerNode sends the analysis result and dynamic classification labels to the LLM for classification. The LLM responds with a **tool-call response format** (function_call with WorkerRouteLabel enum values as valid labels). This matches the established DecisionNode pattern where `_classification_call()` builds classification messages with label options and `_dispatch_route()` uses word-boundary matching to extract the selected label.
3. **Validated RouteMap dispatch**: WorkerNode validates the classification label against the dynamic labels and dispatches to the corresponding route handler.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Invalid or missing classification label | `NodeRetryPolicy` retry (default max_attempts=3, on_retry_exhausted="raise") | After max attempts, `NodeExecutionError` is raised |
| Empty or null input reaching WorkerNode during LLM decision | Pass through original input unchanged | LLM decision process handles empty context gracefully |
| Passthrough classified but no worker-spawned node exists | Dynamic label exclusion prevents this; if somehow classified, route handler checks `queue.find_worker_spawned_nodes()` and raises `NodeExecutionError` if empty | Defensive validation in route handler |
| No terminal response after clear | `ensure_terminal()` adds default | Route handler responsibility |
| WorkerNode has no session attached | `NodeExecutionError` | Consistent with Milestone 2.2 behavior |
| LLM call fails | `NodeRetryPolicy` retry | Standard LLM failure handling |

### Input Preservation (FR-013)

WorkerNode preserves the original input query for downstream nodes:

1. **Storage**: WorkerNode stores the original input on `self._last_input` before calling `super().__call__()` for LLM decision.
2. **Route handlers**: Each route handler receives `self` (via the method call), so `_last_input` is accessible as `self._last_input`.
3. **Passthrough**: The `passthrough` handler calls `queue.set_input(next_node, self._last_input)` to forward the original input to the next worker-spawned node.
4. **Other routes**: task_recreation, task_reanalysis, and proceed_execution don't need to forward input since they spawn new nodes that receive the session context.

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Add four new route labels to WorkerRouteLabel enum (FR-004)
- [ ] Implement `_has_worker_spawned_nodes()` (FR-003)
- [ ] Implement `_get_classification_labels()` for dynamic label adjustment (FR-003)
- [ ] Update `_build_default_route_map()` to register all five route labels (FR-007)
- [ ] Implement `_route_task_recreation()` handler (FR-008)
- [ ] Implement `_route_task_reanalysis()` handler (FR-009)
- [ ] Implement `_route_passthrough()` handler (FR-010, FR-013)
- [ ] Implement `_route_proceed_execution()` handler (FR-011)
- [ ] Update `__call__()` to use dynamic labels when task exists (FR-001, FR-002, FR-003)
- [ ] Add NodeRetryPolicy integration for invalid classification labels (FR-006)
- [ ] Add `ensure_terminal()` calls in all new route handlers (FR-012)
- [ ] Ensure WorkerNode tool scope is restricted to decision tools only (FR-014)
- [ ] Verify queue invariant: QueryAnalyst remains first after dispatch (FR-016)
- [ ] Write unit tests for all new components
- [ ] Write integration tests for worker LLM decision flow

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Implement TaskAnalyzerNode full behavior (Milestone 2.4)
- [ ] Implement TaskExecutor and ResultReviewer path (Milestone 3.2)

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: WorkerNode uses dynamic classification labels based on worker-spawned node presence
   - **Reason**: Passthrough is only meaningful when a worker-spawned node exists to receive it. Including it when no such node exists would lead to invalid routing.
   - **Alternatives Considered**: Static labels with runtime validation — rejected because it adds unnecessary complexity and LLM confusion from invalid options.

2. **Decision**: Route handlers follow the same pattern as task_creation (clear → spawn → ensure_terminal)
   - **Reason**: Consistency with Milestone 2.2 patterns; all route handlers that clear the queue must ensure terminal response path.
   - **Alternatives Considered**: Different patterns per route — rejected because it complicates maintenance and testing.

3. **Decision**: passthrough route handler uses `queue.advance()` without re-inserting WorkerNode
   - **Reason**: WorkerNode is a transient routing node; after forwarding input, it should not remain in the active path. The next worker-spawned node takes over.
   - **Alternatives Considered**: Re-insert WorkerNode after passthrough — rejected because it creates unnecessary queue cycling and complicates the terminal response path.

4. **Decision**: proceed_execution ensures terminal response path (spawning deferred to Milestone 3.2)
   - **Reason**: TaskExecutor and ResultReviewer classes do not exist yet. The handler logs the classification and ensures the terminal response path exists. Full implementation is deferred to Milestone 3.2.
   - **Alternatives Considered**: Spawn placeholder nodes — rejected because it adds complexity without functional value.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Dynamic label adjustment could cause inconsistent LLM responses | Low | Medium | Comprehensive unit tests for label adjustment; LLM sees only valid options |
| passthrough route handler could leave queue in inconsistent state | Medium | High | Defensive validation in route handler; ensure_terminal() call |
| proceed_execution handler could leave queue without terminal path | Medium | High | ensure_terminal() call in all route handlers |
| NodeRetryPolicy could cause infinite loop for persistent invalid labels | Low | Low | Max retries limit (default 3); NodeExecutionError after exhaustion |
| LLM classification could be ambiguous between task_recreation and task_reanalysis | Medium | Medium | Clear system prompt differentiation; NodeRetryPolicy for retries |

---

## Design Decisions

1. **WorkerNode always retries via NodeRetryPolicy for unrecognized labels**
   - No fallback route is needed since all five labels are valid in this milestone. This decision is consistent with QueryAnalyst's retry behavior.

2. **TaskAnalyzerNode tool scope is determined by route handler, not WorkerNode**
   - Route handlers (task_recreation, task_reanalysis) create TaskAnalyzerNode with appropriate tool scope. This keeps tool scope management close to the route logic.

3. **passthrough does not re-insert WorkerNode**
   - WorkerNode is a transient routing node. After forwarding input, the next worker-spawned node takes over. This simplifies queue management and avoids unnecessary cycling.

4. **proceed_execution ensures terminal response path (spawning deferred to Milestone 3.2)**
   - TaskExecutor and ResultReviewer classes do not exist yet. The handler logs the classification and ensures the terminal response path exists. Full implementation is deferred to Milestone 3.2.

---

## References

- Spec: `./spec.md` — relative path from this design.md to its spec.md
- Related designs:
  - `src/tinycua/specs/2.2-worker-node-deterministic-routing/spec.md` — Milestone 2.2 spec (prerequisite)
  - `src/tinycua/specs/2.1-route-map-query-analyst/spec.md` — Milestone 2.1 spec (prerequisite)
  - `src/tinycua/docs/design/loops/worker_concept.md` — WorkerNode concept design (full coverage in this milestone)
  - `src/tinycua/docs/design/loops/worker.md` — WorkerNode detailed design (full coverage in this milestone)
  - `src/tinycua/docs/design/models/classification.md` — Classification model design (full coverage in this milestone)
