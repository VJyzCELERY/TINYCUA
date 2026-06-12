# Design Document: TinyCUAResultAggregationNode

**Spec**: `./spec.md`
**Status**: Implemented
**Last Updated**: 2026-06-11

---

## Overview

This design introduces `TinyCUAResultAggregationNode` — a `ProcessNode` that performs read-only traversal of the accepted root task tree, consolidates task results/artifacts/reviewer decisions, and produces an `AggregatedResult` for `TinyCUAResponseNode`. The design follows `src/tinycua/docs/design/loops/result_aggregation.md`, `src/tinycua/docs/design/loops/node.md`, and `src/tinycua/docs/design/models/task.md`. It wires root-task-accept routing in `TinyCUALoop` so that when `ResultReviewer` accepts the root task, the queue advances through `ResultAggregationNode` → `TinyCUAResponseNode`.

---

## Architecture

### Component Overview

```
TinyCUALoop._on_reviewer_accept(task)
  │
  ├── If task is root (no parent):
  │     clear_after_current()
  │     spawn [ResultAggregationNode, TinyCUAResponseNode]
  │     ensure_terminal(TinyCUAResponseNode)
  │
  ├── If task is not root:
  │     (existing behavior — advance to next active task)
  │
ResultAggregationNode.__call__(input)
  │
  ├── 1. Guard: assert root task is done
  ├── 2. Traverse task tree (guided BFS right-to-left)
  │     For each inspected task:
  │       - Collect task summary
  │       - Collect TaskResult (if present)
  │       - Collect artifacts (if present)
  │       - Collect reviewer decision (if present)
  │       - Check if sufficient context gathered → may stop early
  ├── 3. Build AggregatedResult
  ├── 4. Record to session context
  └── 5. propagate()

on_complete():
  └── queue.advance() → TinyCUAResponseNode receives AggregatedResult
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops.result_aggregation` (new) | New | Module containing `TinyCUAResultAggregationNode` and `AggregatedResult` |
| `tinycua.loops.__init__` | Modified | Export new classes |
| `tinycua.loops.tinycua_loop` | Modified | Wire root-task-accept → aggregation in `_on_reviewer_accept` |

---

## Data Model

### New Entities

```python
from dataclasses import dataclass, field

@dataclass
class AggregatedResult:
    """Consolidated result from traversing an accepted root task tree.

    Attributes:
        root_task_id: The ID of the root task that was accepted.
        task_summaries: Human-readable summaries of each inspected task.
        accepted_results: TaskResult objects from accepted tasks.
        artifacts: Artifact dicts collected from task results.
        final_context: Consolidated context string for TinyCUAResponseNode. Built by joining
            each task summary ("{title}: {summary}" or "{title}: not_executed") with
            newline separators, prefixed with the root task title.
        response_continuation: Continuation text to guide TinyCUAResponseNode synthesis.
            Implementation-defined for MVP; empty string is valid.
        metadata: Additional metadata (traversal depth, count of tasks inspected, etc.).
    """
    root_task_id: str
    task_summaries: list[str] = field(default_factory=list)
    accepted_results: list[TaskResult] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    final_context: str = ""
    response_continuation: str = ""
    metadata: dict = field(default_factory=dict)
```

The `AggregatedResult` dataclass is defined in `tinycua.loops.result_aggregation` and re-exported from `tinycua.loops`.

---

## API / Interface Contracts

### TinyCUAResultAggregationNode

```python
class TinyCUAResultAggregationNode(ProcessNode):
    """Read-only aggregation node for accepted root task trees.

    Traverses the completed task tree using guided BFS right-to-left,
    consolidates results/artifacts/decisions, and emits AggregatedResult.
    """

    def __init__(
        self,
        node_id: str = "result_aggregation",
        config: NodeConfigBase | None = None,
        loop: Any | None = None,
    ) -> None:
        ...

    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute aggregation.

        Args:
            input: NodeInput containing root task reference.

        Returns:
            LLMResult with AggregatedResult in metadata.
        """

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Advance queue to the next node (expected: TinyCUAResponseNode)."""
```

### TinyCUAResponseNode Input Contract

`TinyCUAResponseNode` (Milestone 3.5) expects the following inputs from upstream nodes:

| Input Source | Expected Content | How AggregatedResult Maps |
|--------------|------------------|---------------------------|
| `AggregatedResult` (from `ResultAggregationNode`) | Task summaries, accepted results, artifacts, final context, response continuation | `aggregated_result.task_summaries`, `.accepted_results`, `.artifacts`, `.final_context`, `.response_continuation` |
| Accumulated root/session context | Prior session messages and context | Already available via `session.context` |
| Latest propagated node output | Output from the previous node in queue | `AggregatedResult` is propagated as the node output |

The `AggregatedResult` fields map directly to `TinyCUAResponseNode`'s LLM input construction:
- `final_context` → consolidated context string for response synthesis
- `response_continuation` → guidance text for continuation of the response
- `task_summaries` → human-readable summaries for grounding the response
- `accepted_results` → structured `TaskResult` objects for detailed inspection
- `artifacts` → artifact dicts for file/reference inclusion

See `src/tinycua/docs/design/loops/response.md` for the full `TinyCUAResponseNode` design.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Root task not done | `NodeExecutionError` | Guard: should not be entered if root task isn't done |
| No session attached | `NodeExecutionError` | Standard ProcessNode contract |
| Empty task tree (root only) | Valid — single-task AggregatedResult | Not an error |
| Task has no result | Skipped in traversal | `task_summary` records "not_executed" |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [x] **AggregatedResult dataclass**: Define `AggregatedResult` with all fields in `tinycua/loops/result_aggregation.py`.
- [x] **BFS traversal helper**: Implement `_traverse_bfs_right_to_left(task_tree, max_inspected_tasks=None, context_sufficient_fn=None) -> Iterator[Task]`.
  - `context_sufficient_fn` signature: `Optional[Callable[[Task, AggregatedResult], bool]]`
    - Called for each inspected task with `(current_task, partial_result)`.
    - Return `True` to stop traversal early (context sufficient).
    - Ignored in MVP; default `None` means no callback.
- [x] **TinyCUAResultAggregationNode class**: Implement `ProcessNode` subclass with:
  - `__call__`: guard check, traversal, consolidation, recording.
  - `_consolidate(traversal_results) -> AggregatedResult`: build final result.
  - `on_complete`: queue advancement.
- [x] **Loop wiring**: Modify `TinyCUALoop._on_reviewer_accept` to detect root task accept and spawn `[ResultAggregationNode, TinyCUAResponseNode]`.
- [x] **Module exports**: Add to `tinycua/loops/__init__.py`.
- [x] **Tests**: Unit tests for AggregatedResult, traversal, and node behavior. Integration test for root-task-accept → aggregation → response path.

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] **Selective deeper reads**: Implement heuristic for early termination based on context sufficiency (e.g., token budget, number of results collected). This is described in the design docs as "may stop early" behavior and should be functional in MVP as a simple threshold (stop after N tasks inspected), then enhanced later.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use a generator-based BFS traversal helper rather than recursive DFS.
   - **Reason**: BFS right-to-left matches the design contract ("most-recent-first"). A generator allows lazy/easy early termination — the caller can simply stop iterating when sufficient context is gathered.
   - **Alternatives Considered**: Recursive DFS (wrong traversal order), iterative DFS with a stack (would need reversal), eager BFS that collects all nodes before inspection (defeats early termination).

2. **Decision**: Co-locate `AggregatedResult` with the node in `tinycua.loops.result_aggregation`.
   - **Reason**: The model is only used by `ResultAggregationNode` and `TinyCUAResponseNode`. Keeping it in the same module avoids cross-package dependency friction. It is re-exported from `tinycua.loops` for convenience.
   - **Alternatives Considered**: `tinycua.models` — too generic; the model is specific to the aggregation workflow.

3. **Decision**: The node does NOT use an LLM call; it is a pure processing node that inspects the in-memory task tree.
   - **Reason**: Aggregation is a mechanical consolidation operation — no LLM inference is needed. The existing task data (summaries, results, artifacts) is already structured.
   - **Alternatives Considered**: LLM-based summary of the entire task tree — deferred to potential Phase 2 enhancement.

4. **Decision**: "Sufficient response-ready context" is defined as having inspected at least one task with an accepted result (`TaskResult` with `execution_status == "succeeded"`) AND at least one artifact, OR reaching the configurable `max_inspected_tasks` threshold.
   - **Reason**: Provides a concrete, testable criterion for early termination. The MVP phase uses `max_inspected_tasks` as the primary threshold; the "one result + one artifact" heuristic is an optional optimization that can be enabled in Phase 2.
   - **Alternatives Considered**: Token-budget-based sufficiency (deferred to Phase 2); purely random sampling (not deterministic).

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Task tree is very deep/wide, causing slow traversal | Low | Medium | Early termination heuristic stops after sufficient context; `max_inspected_tasks` config limits the count of inspected tasks. |
| `AggregatedResult` grows too large for LLM context window | Low | Medium | `final_context` and `task_summaries` are produced from existing summaries; aggregation does not add new content. TinyCUAResponseNode is responsible for context window management. |
| Loop wiring breaks existing accept path for non-root tasks | Low | High | Guard the root-task check explicitly: only route to aggregation when `task.parent is None`. Non-root accept continues with existing behavior. |

---

## Open Questions _(optional)_

1. **How does `TinyCUAResultAggregationNode` receive the root task reference?**
   - **Proposed Answer**: Via `NodeInput.metadata["root_task_id"]` or by accessing `session.task` (the root task). This is decided in favor of `session.task` since the root task is already stored on the session.

---

## References

- Spec: `./spec.md`
- Related designs:
  - `src/tinycua/docs/design/loops/result_aggregation.md` — Target architecture for this node
  - `src/tinycua/docs/design/loops/node.md` — Base node hierarchy and responsibility separation
  - `src/tinycua/docs/design/models/task.md` — Task model with active task lifecycle and root-task-done routing
  - `src/tinycua/docs/design/loops/response.md` — TinyCUAResponseNode input contract
  - `src/tinycua/docs/design/loops/result_reviewer.md` — ResultReviewer accept path that triggers aggregation
  - Existing implementations: `tinycua/loops/result_reviewer.py`, `tinycua/loops/response_node.py`
