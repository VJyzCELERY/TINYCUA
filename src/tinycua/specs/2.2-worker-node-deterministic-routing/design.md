# Design Document: TinyCUAWorkerNode Deterministic Routing and TaskCreate

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-08

---

## Overview

This design implements deterministic task-creation routing for TinyCUAWorkerNode and introduces TinyCUATaskCreateNode as a concrete ProcessNode for first-time root task creation. WorkerNode gains the ability to detect missing tasks and route deterministically to `task_creation` without LLM decisions, while TaskCreateNode handles root task creation using TaskInit/TaskCreate tools. This milestone establishes the foundational worker-owned queue segment management and terminal response path guarantees.

---

## Architecture

### Component Overview

```
[QueryAnalyst] --> [WorkerNode] --> [TaskCreateNode] --> [TaskAnalyzerNode] --> [AnalysisEffortNode] --> [TaskExecutor] --> [ResultReviewer] --> [ResponseNode]
                     |                ← worker-owned segment →                      |
                     └── (task_creation route, deterministic)     ensure_terminal()
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops.worker.TinyCUAWorkerNode` | New | Concrete DecisionNode with route_map for task_creation routing |
| `tinycua.loops.task_create.TinyCUATaskCreateNode` | New | ProcessNode for deterministic root task creation |
| `tinycua.loops.task_analyzer.TinyCUATaskAnalyzerNode` | New | ProcessNode with mode=initial_analysis without TaskInit/TaskCreate tools |
| `tinycua.loops.node_queue.NodeQueue` | Modified | Add `find_worker_spawned_nodes()` and `find_existing_worker_node()` for worker-spawned-node detection; `ensure_terminal()` already exists |

---

## Data Model

### New Entities

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# WorkerNode route labels (subset implemented in this milestone)
class WorkerRouteLabel(str, Enum):
    task_creation = "task_creation"            # Deterministic, no LLM
    task_recreation = "task_recreation"        # NOT IN SCOPE — Milestone 2.3
    task_reanalysis = "task_reanalysis"        # NOT IN SCOPE — Milestone 2.3
    passthrough = "passthrough"                # NOT IN SCOPE — Milestone 2.3
    proceed_execution = "proceed_execution"    # NOT IN SCOPE — Milestone 2.3

# TaskCreateNode output
@dataclass
class TaskCreateResult:
    task_id: str           # ID of created root task
    task_summary: str      # Summary of what was created
    created_at: datetime   # Timestamp of creation
```

### Schema Changes

- No schema changes to existing data structures.
- WorkerNode route_map is a new attribute on the DecisionNode instance.

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
        WorkerNode entry point. Performs deterministic prechecks before LLM decision.
        For this milestone, only task_creation is implemented deterministically.
        WorkerNode MUST pass through empty/null input without modification.
        Downstream nodes handle empty input per their own policies.
        """
    
    def _detect_task_exists(self, context: NodeContext) -> bool:
        """Check if a task already exists in the session via session.task (the Session model already has a task attribute)."""
    
    def _detect_worker_spawned_nodes(self, queue: NodeQueue) -> list[Node]:
        """Find worker-owned nodes in the queue before terminal ResponseNode."""
    
    def _route_task_creation(self, queue: NodeQueue, result: DecisionResult) -> NodeOutput:
        """Deterministic route: spawn TaskCreateNode for root task creation."""
```

```python
class TinyCUATaskCreateNode(ProcessNode):
    """
    Concrete ProcessNode for deterministic first-time root task creation.
    Uses only TaskInit/TaskCreate tools.
    """
    
    tool_scope: list[str] = ["TaskInit", "TaskCreate"]
    
    def __call__(self, input: NodeInputLike) -> LLMResult:
        """
        Create root task deterministically and advance queue.
        Returns LLMResult with task_id, task_summary, and created_at.
        Next node is TaskAnalyzerNode (without TaskInit/TaskCreate tools).
        """
    
    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Advance queue; next node is TaskAnalyzerNode."""
```

```python
# NodeQueue additions
class NodeQueue:
    def find_worker_spawned_nodes(self) -> list[Node]:
        """Find all nodes spawned by WorkerNode before terminal ResponseNode."""
    
    def find_existing_worker_node(self) -> Optional[TinyCUAWorkerNode]:
        """Find existing WorkerNode in queue before terminal ResponseNode.
        
        This is the source of truth for worker-node lookup. QueryAnalyst's
        find_existing_worker() (query_analyst.py:131) should delegate to this
        method to avoid logic duplication.
        """
    
    def ensure_terminal(self, default_response_node: Node) -> None:
        """Ensure terminal response path exists after clear operations."""
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Empty or null input reaching WorkerNode | Pass through original input unchanged | Downstream nodes handle per their own policies |
| TaskCreateNode fails to create root task | `NodeRetryPolicy` retry (TaskCreateNode's own config) | After max retries, failure propagates to WorkerNode which must handle the error (e.g., return error to user). Downstream nodes never receive a valid task tree. |
| No terminal response after clear | `ensure_terminal()` adds default | Route handler responsibility |
| Invalid WorkerNode route label | `NodeRetryPolicy` retry | Only `task_creation` valid in this milestone |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Implement TinyCUAWorkerNode with route_map containing `task_creation` label
- [ ] Implement `_detect_task_exists()` to check session for existing task
- [ ] Implement `_detect_worker_spawned_nodes()` to find worker-owned nodes
- [ ] Implement `_route_task_creation()` handler that spawns TaskCreateNode
- [ ] Implement TinyCUATaskCreateNode with TaskInit/TaskCreate tool scope
- [ ] Implement TaskCreateNode `on_complete()` to advance queue to TaskAnalyzerNode
- [ ] Add `find_worker_spawned_nodes()` and `find_existing_worker_node()` to NodeQueue (existing: `clear_after_current()`, `ensure_terminal()`)
- [ ] Update route handlers calling `clear_after_current()` to use `ensure_terminal()`
- [ ] Add mode=initial_analysis to TaskAnalyzerNode (without TaskInit/TaskCreate tools)
- [ ] Add tool_scope to TaskAnalyzerNode for initial_analysis mode (exclude TaskInit/TaskCreate tools)
- [ ] Write unit tests for all new components
- [ ] Write integration tests for worker task_creation flow

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Implement remaining worker route labels (task_recreation, task_reanalysis, passthrough, proceed_execution) — Milestone 2.3
- [ ] Implement LLM decision process for non-deterministic routes — Milestone 2.3

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: WorkerNode performs deterministic precheck for `task_creation` before LLM decision
   - **Reason**: When no task exists, LLM decision is unnecessary — the route is deterministic. This avoids unnecessary LLM calls and simplifies the first-time creation flow.
   - **Alternatives Considered**: Always use LLM decision — rejected because it adds latency and cost for a deterministic case.

2. **Decision**: TaskCreateNode is a separate ProcessNode, not a method on WorkerNode
   - **Reason**: Separation of concerns — WorkerNode handles routing, TaskCreateNode handles task creation. This allows TaskCreateNode to have its own tool scope and retry policy.
   - **Alternatives Considered**: Inline task creation in WorkerNode — rejected because it violates single responsibility and complicates tool scope management.

3. **Decision**: Worker-spawned-node detection uses queue position before terminal ResponseNode
   - **Reason**: Matches the design doc's "Worker-Route Rule" — worker-owned segment is bounded by the terminal ResponseNode. This is consistent with QueryAnalyst's WorkerNode detection logic.
   - **Alternatives Considered**: Tagging nodes with metadata — rejected because it adds complexity without benefit; queue position is sufficient.

4. **Decision**: `ensure_terminal()` is a NodeQueue method called by route handlers
   - **Reason**: Route handlers are responsible for maintaining queue invariants after `clear_after_current()`. This keeps the guarantee close to the mutation point.
   - **Alternatives Considered**: Automatic guarantee in `clear_after_current()` — rejected because not all clears need to ensure terminal (some may be partial clears).

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| WorkerNode route_map incomplete for non-task_creation routes | Low | Medium | Phase 2 defers remaining routes; only task_creation is required |
| TaskCreateNode retry loop could block queue | Low | Low | NodeRetryPolicy with max retries; failure propagates to WorkerNode |
| `ensure_terminal()` called incorrectly by route handlers | Medium | High | Comprehensive unit tests for all route handlers; code review checklist |
| Worker-spawned-node detection misses nodes due to queue ordering | Low | High | Tests verify detection with various queue shapes; consistent with QueryAnalyst logic |

---

## Design Decisions

1. **WorkerNode uses retry, not default route, for unrecognized labels**
   - WorkerNode always retries via NodeRetryPolicy for unrecognized labels. No fallback route is needed since only `task_creation` is valid in this milestone. This decision will be revisited in Milestone 2.3 when additional routes are added.

2. **TaskCreateNode emits INFO-level log for task creation**
   - TaskCreateNode logs task ID and summary at INFO level for observability. This provides traceability without requiring external event infrastructure.

---

## References

- Spec: `./spec.md` — relative path from this design.md to its spec.md
- Related designs:
  - `src/tinycua/specs/2.1-route-map-query-analyst/spec.md` — Milestone 2.1 spec (prerequisite)
