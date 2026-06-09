# Design Document: TinyCUAAnalysisEffortNode

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-09

---

## Overview

This design implements `TinyCUAAnalysisEffortNode`, a deterministic `ProcessNode` that controls how many upfront task-assessment and task-analysis passes occur before advancing to execution. It is inserted by WorkerNode route handlers as part of the Worker's planning segment and runs without LLM calls. The node maps `WorkerEffort` levels (`none`, `low`, `medium`, `high`) to pass limits (0, 1, 2, 3), prepends `[TaskAssessor, TaskAnalyzer]` pairs until the threshold is reached, and spawns TaskExecutor before advancing when the threshold is met. WorkerNode route handlers are updated to insert AnalysisEffortNode after the initial TaskCreate/TaskAnalyzer in the queue.

---

## Architecture

### Component Overview

```
[WorkerNode] --> [TaskCreate/TaskAnalyzer] --> [AnalysisEffortNode] --> [TaskExecutor] --> [ResultReviewer] --> [ResponseNode]
                         |                           |
                         |                      pass_count < pass_limit?
                         |                         ├── Yes: prepend [TaskAssessor, TaskAnalyzer]
                         |                         │         pass_count += 1
                         |                         │         re-enter AnalysisEffortNode
                         |                         └── No: spawn TaskExecutor, advance
                         |
                    (initial pass)
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops.analysis_effort.TinyCUAAnalysisEffortNode` | New | Deterministic ProcessNode for effort control |
| `tinycua.loops.analysis_effort.WorkerEffort` | New | Enum for effort levels |
| `tinycua.loops.analysis_effort.effort_to_pass_limit()` | New | Mapping function from effort to pass limit |
| `tinycua.loops.task_assessor.TinyCUATaskAssessorNode` | New | ProcessNode for task tree evaluation and selection (effort-loop mode) |
| `tinycua.loops.worker.TinyCUAWorkerNode` | Modified | Route handlers insert AnalysisEffortNode after TaskCreate/TaskAnalyzer |
| `tinycua.loops.worker.WorkerRouteLabel` | Modified | No change to labels, but route handler queue shapes updated |

---

## Data Model

### New Entities

```python
from enum import Enum

class WorkerEffort(str, Enum):
    """Effort levels for task analysis passes.
    
    Controls how many [TaskAssessor, TaskAnalyzer] rounds precede execution.
    """
    none = "none"      # pass_limit=0: skip extra analysis, advance directly to executor
    low = "low"        # pass_limit=1: one extra [TaskAssessor, TaskAnalyzer] pass
    medium = "medium"  # pass_limit=2: two extra passes
    high = "high"      # pass_limit=3: three extra passes


def effort_to_pass_limit(effort: WorkerEffort) -> int:
    """Map WorkerEffort to pass limit.
    
    Args:
        effort: The configured effort level.
    
    Returns:
        Number of [TaskAssessor, TaskAnalyzer] passes to prepend.
    """
    return {
        WorkerEffort.none: 0,
        WorkerEffort.low: 1,
        WorkerEffort.medium: 2,
        WorkerEffort.high: 3,
    }[effort]
```

### Pass Count Tracking

AnalysisEffortNode tracks `pass_count` as an instance attribute, initialized to 0. Each time a `[TaskAssessor, TaskAnalyzer]` pair is prepended, `pass_count` is incremented. When `pass_count >= pass_limit`, the node spawns TaskExecutor.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
class TinyCUAAnalysisEffortNode(ProcessNode):
    """Deterministic ProcessNode that controls planning depth.
    
    Maps WorkerEffort to pass limits and prepends [TaskAssessor, TaskAnalyzer]
    pairs until the threshold is reached. When threshold is reached, spawns
    TaskExecutor before advancing.
    
    Attributes:
        node_id: Always "analysis_effort" by default.
        effort: The configured WorkerEffort level.
        pass_limit: Derived from effort via effort_to_pass_limit().
        pass_count: Current number of passes completed (starts at 0).
    """
    
    def __init__(
        self,
        node_id: str = "analysis_effort",
        config: NodeConfigBase | None = None,
        effort: WorkerEffort = WorkerEffort.none,
    ) -> None:
        """Initialize AnalysisEffortNode.
        
        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            effort: The configured effort level. Defaults to "none".
        """
    
    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute the effort control logic.
        
        Deterministic behavior:
        - If pass_count < pass_limit: prepend [TaskAssessor, TaskAnalyzer],
          increment pass_count, return a summary response.
        - If pass_count >= pass_limit: spawn TaskExecutor, return a summary response.
        
        Args:
            input: The node input (ignored for deterministic logic).
        
        Returns:
            LLMResult with summary of effort control action taken.
        """
    
    def _should_spawn_executor(self) -> bool:
        """Check if pass_limit has been reached.
        
        Returns:
            True if pass_count >= pass_limit, False otherwise.
        """
    
    def _prepend_assessor_analyzer_pair(self, queue: NodeQueue) -> None:
        """Prepend a [TaskAssessor, TaskAnalyzer] pair to the queue.
        
        Creates TinyCUATaskAssessorNode (mode=effort_loop) and
        TinyCUATaskAnalyzerNode (mode=effort_loop_decomposition),
        prepends them before the current node position.
        
        Args:
            queue: The node queue to mutate.
        """
    
    def _spawn_task_executor(self, queue: NodeQueue) -> None:
        """Spawn TaskExecutor and ensure terminal response path.
        
        Creates TinyCUATaskExecutorNode and spawns it after the current
        position, ensuring terminal response path is maintained.
        
        Args:
            queue: The node queue to mutate.
        """
    
    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Post-completion hook for queue mutations.
        
        Called by the orchestrator after __call__ completes. Handles the
        queue mutations (prepending or spawning) based on pass_count state.
        
        Args:
            queue: The node queue (may be mutated).
            response: The summary response from __call__.
        """
```

### WorkerNode Route Handler Modifications

WorkerNode route handlers are updated to insert AnalysisEffortNode after the initial TaskCreate/TaskAnalyzer:

```python
class TinyCUAWorkerNode(DecisionNode):
    # ... existing code ...
    
    def _route_task_creation(self, queue: NodeQueue, result: DecisionResult) -> None:
        """Deterministic route: spawn TaskCreateNode then TaskAnalyzerNode then AnalysisEffortNode."""
        from tinycua.loops.analysis_effort import TinyCUAAnalysisEffortNode
        from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode
        from tinycua.loops.task_create import TinyCUATaskCreateNode
        
        queue.clear_after_current()
        
        task_create = TinyCUATaskCreateNode(node_id="task_create", config=self.config)
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=self.config, mode="initial_analysis",
        )
        analysis_effort = TinyCUAAnalysisEffortNode(
            node_id="analysis_effort", config=self.config, effort=self._effort,
        )
        queue.spawn_after_current([task_create, task_analyzer, analysis_effort])
        queue.ensure_terminal(self.default_response_node)
    
    def _route_task_recreation(self, queue: NodeQueue, result: DecisionResult) -> None:
        """LLM-assisted route: clear + spawn TaskAnalyzerNode + AnalysisEffortNode."""
        from tinycua.loops.analysis_effort import TinyCUAAnalysisEffortNode
        from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode
        
        queue.clear_after_current()
        
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=self.config, mode="analysis",
        )
        analysis_effort = TinyCUAAnalysisEffortNode(
            node_id="analysis_effort", config=self.config, effort=self._effort,
        )
        queue.spawn_after_current([task_analyzer, analysis_effort])
        queue.ensure_terminal(self.default_response_node)
    
    def _route_task_reanalysis(self, queue: NodeQueue, result: DecisionResult) -> None:
        """LLM-assisted route: clear + spawn TaskAnalyzerNode + AnalysisEffortNode."""
        from tinycua.loops.analysis_effort import TinyCUAAnalysisEffortNode
        from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode
        
        queue.clear_after_current()
        
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=self.config, mode="initial_analysis",
        )
        analysis_effort = TinyCUAAnalysisEffortNode(
            node_id="analysis_effort", config=self.config, effort=self._effort,
        )
        queue.spawn_after_current([task_analyzer, analysis_effort])
        queue.ensure_terminal(self.default_response_node)
```

### Updated Queue Shapes

```text
task_creation:
  [TaskCreateNode, TaskAnalyzerNode(initial_analysis), AnalysisEffortNode, TaskExecutor, ResultReviewer, ResponseNode]

task_recreation:
  [TaskAnalyzerNode(analysis), AnalysisEffortNode, TaskExecutor, ResultReviewer, ResponseNode]

task_reanalysis:
  [TaskAnalyzerNode(initial_analysis), AnalysisEffortNode, TaskExecutor, ResultReviewer, ResponseNode]

proceed_execution:
  [TaskExecutor, ResultReviewer, ResponseNode]
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| WorkerEffort not configured | Default to `WorkerEffort.none` (pass_limit=0) | Safe default: skip extra passes |
| pass_count reaches pass_limit | Spawn TaskExecutor, advance queue | Prevents queue drain |
| TaskAssessor selects no tasks | No TaskAnalyzer spawned; queue advances back to AnalysisEffortNode | Pass still counts |
| AnalysisEffortNode has no session attached | `NodeExecutionError` | Consistent with ProcessNode behavior |
| Queue mutation fails | `NodeExecutionError` | Standard queue error handling |
| Route handler modifies queue after AnalysisEffortNode prepends | AnalysisEffortNode re-evaluates pass_count on re-entry | Route handlers call `clear_after_current()` which removes stale passes; pass_count resets for the new effort cycle |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create `WorkerEffort` enum (FR-003)
- [ ] Implement `effort_to_pass_limit()` mapping function (FR-004)
- [ ] Create `TinyCUAAnalysisEffortNode` class with pass counting (FR-001, FR-002, FR-005, FR-006, FR-007)
- [ ] Implement `_prepend_assessor_analyzer_pair()` (FR-006)
- [ ] Implement `_spawn_task_executor()` with terminal path maintenance (FR-007, FR-008)
- [ ] Implement `on_complete()` for queue mutations (FR-005, FR-006, FR-007)
- [ ] Update WorkerNode `_route_task_creation()` to insert AnalysisEffortNode (FR-009)
- [ ] Update WorkerNode `_route_task_recreation()` to insert AnalysisEffortNode (FR-009)
- [ ] Update WorkerNode `_route_task_reanalysis()` to insert AnalysisEffortNode (FR-009)
- [ ] Add default effort configuration to WorkerNode (FR-010)
- [ ] Write unit tests for all acceptance scenarios
- [ ] Write integration tests for worker → effort → executor flow

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Implement TaskExecutor and ResultReviewer path (Milestone 3.2)
- [ ] Implement full effort loop with TaskAssessor/TaskAnalyzer integration

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: AnalysisEffortNode is a deterministic ProcessNode (no LLM call)
   - **Reason**: The effort control logic is purely algorithmic — counting passes and prepending nodes. No LLM decision is needed.
   - **Alternatives Considered**: LLM-based effort decision — rejected because it adds unnecessary latency and cost for a deterministic operation.

2. **Decision**: WorkerEffort maps to discrete pass limits (0, 1, 2, 3) rather than continuous values
   - **Reason**: Discrete levels are simpler to configure, test, and reason about. The architecture design specifies exactly these four levels.
   - **Alternatives Considered**: Continuous pass count — rejected because it complicates configuration and testing without clear benefit.

3. **Decision**: AnalysisEffortNode is inserted by WorkerNode route handlers, not owned by WorkerNode
   - **Reason**: AnalysisEffortNode is a standalone node in the queue. WorkerNode route handlers insert it as part of the queue shape. This keeps the node independent and testable.
   - **Alternatives Considered**: WorkerNode owns AnalysisEffortNode as a child — rejected because it complicates the parent-child session adoption model.

4. **Decision**: pass_count resets when queue is cleared by a route handler
   - **Reason**: When a route handler calls `clear_after_current()`, stale effort passes are removed. AnalysisEffortNode re-enters with pass_count=0 for the new effort cycle.
   - **Alternatives Considered**: Persist pass_count across route changes — rejected because it creates inconsistency when the task tree is rebuilt.

5. **Decision**: TaskAssessor no-tasks-selected path advances back to AnalysisEffortNode
   - **Reason**: The effort loop must continue counting passes even when no tasks are selected. This ensures the pass limit is respected regardless of task tree state.
   - **Alternatives Considered**: Skip remaining passes when no tasks selected — rejected because it bypasses the configured effort level.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| AnalysisEffortNode could create infinite loop if pass_count never increments | Low | High | pass_count is incremented atomically before prepending; on_complete is called exactly once per pass |
| WorkerNode route handlers could forget to insert AnalysisEffortNode | Medium | Medium | Comprehensive unit tests for all route shapes; integration tests verify queue shape |
| TaskAssessor no-tasks path could bypass effort counting | Low | Medium | pass_count increments regardless of TaskAssessor selection; integration test verifies |
| Terminal response path could be lost after TaskExecutor spawning | Medium | High | ensure_terminal() call in _spawn_task_executor(); unit test verifies |
| WorkerEffort default could be wrong | Low | Low | Default to "none" (pass_limit=0) for safe behavior; configurable via WorkerNode |

---

## Design Decisions

1. **AnalysisEffortNode does not call LLM**
   - The effort control logic is purely algorithmic. No LLM decision is needed for counting passes and prepending nodes.

2. **pass_count is an instance attribute, not session state**
   - pass_count is transient and resets when the node is re-created or the queue is cleared. This simplifies the implementation and avoids session pollution.

3. **TaskAssessor uses effort-loop mode when called from AnalysisEffortNode**
   - TaskAssessor has two modes: effort-loop and reviewer-replan. AnalysisEffortNode uses effort-loop mode, which evaluates the full task tree and selects only unfinished tasks.

4. **TaskAnalyzer uses effort_loop_decomposition mode when called from AnalysisEffortNode**
   - TaskAnalyzer has multiple modes. The effort_loop_decomposition mode decomposes tasks selected by TaskAssessor without TaskInit/TaskCreate tools.

5. **WorkerNode stores effort configuration**
   - WorkerNode receives the effort configuration and passes it to AnalysisEffortNode when spawning it. This keeps the configuration close to the WorkerNode that owns the planning decision.

---

## References

- Spec: `./spec.md` — relative path from this design.md to its spec.md
- Related designs:
  - `src/tinycua/docs/design/loops/analysis_effort.md` — Target architecture design (baseline)
  - `src/tinycua/docs/design/loops/worker.md` — WorkerNode design with AnalysisEffortNode integration
  - `src/tinycua/docs/design/loops/task_assessor.md` — TaskAssessor design (effort-loop mode)
  - `src/tinycua/docs/design/loops/task_analyzer.md` — TaskAnalyzer design (effort_loop_decomposition mode)
  - `src/tinycua/specs/2.3-worker-llm-optional-llm-decision/spec.md` — Milestone 2.3 spec (prerequisite)
  - `src/tinycua/specs/2.2-worker-node-deterministic-routing/spec.md` — Milestone 2.2 spec (prerequisite)
