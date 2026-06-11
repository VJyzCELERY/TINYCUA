# Design Document: TinyCUAResultAggregationNode

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-11

---

## Overview

This design introduces `TinyCUAResultAggregationNode` (a concrete `ProcessNode`) into `tinycua.loops`, adds the `AggregatedResult` data model, and wires the post-acceptance path so that after the root task is accepted/done, the loop routes to ResultAggregationNode instead of directly to ResponseNode. The node performs a guided BFS right-to-left / most-recent-first traversal of the root task tree, consolidates task context/results/artifacts/reviewer decisions, and emits an `AggregatedResult` that provides response-ready context for `TinyCUAResponseNode`. The design follows `src/tinycua/docs/design/loops/result_aggregation.md`.

---

## Architecture

### Component Overview

```
TinyCUALoop._on_reviewer_accept(active_task)
  │ (root task, all children complete)
  │
  ├── mark root task done
  ├── route to ResultAggregationNode
  │
  ▼
┌──────────────────────────────────────┐
│  ResultAggregationNode               │  ProcessNode
│  (task tree traversal & aggregation) │  entered only after root task accepted/done
│  → emits AggregatedResult            │  read-only task tree inspection
└────────────────┬─────────────────────┘
                 │
                 │ on_complete → advance queue
                 │ AggregatedResult propagated via standard propagation
                 ▼
┌──────────────────────────────────────┐
│  ResponseNode                        │  ProcessNode
│  (final response synthesis)          │  receives AggregatedResult as context
│  → produces user-facing response     │
└──────────────────────────────────────┘
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops.result_aggregation` | New | New module containing `TinyCUAResultAggregationNode` and `AggregatedResult` |
| `tinycua.loops.tinycua_loop` | Modified | Wire `_on_reviewer_accept` to route to ResultAggregationNode for root task |
| `tinycua.models.aggregated_result` | New | New data model for the aggregation output |
| `tinycua.loops.response` | Reference | ResponseNode consumes `AggregatedResult` (actual ResponseNode changes deferred to Milestone 3.5) |
| `tinycua.config.node_config` | Modified | Add aggregation-related configuration options (threshold for early termination) |
| `tinycua.loops.node_queue` | Reference | Queue advancement: `on_complete` from ResultAggregationNode → next node (ResponseNode) |

---

## Data Model

### New Entities

```python
@dataclass
class AggregatedResult:
    """Consolidated information from task tree traversal for ResponseNode."""
    root_task_id: str                       # The root task that was accepted
    task_summaries: list[str]               # Per-task summary strings from BFS traversal
    accepted_results: list[TaskResult]      # Results from accepted/done tasks
    artifacts: list[dict]                   # Collected artifacts from task tree
    final_context: str                      # Consolidated context string for response synthesis
    response_continuation: str              # Continuation instruction for ResponseNode
    metadata: dict                          # Additional metadata (traversal depth, task count, etc.)
```

### Schema Changes

- No existing data structures are modified.
- `AggregatedResult` is a new standalone model referenced by ResultAggregationNode output.
- No migration required — this is additive.

---

## API / Interface Contracts

### New / Modified Components

```python
class TinyCUAResultAggregationNode(ProcessNode):
    """
    A concrete ProcessNode that traverses the root task tree after root task
    acceptance, consolidates task context/results/artifacts/reviewer decisions,
    and emits an AggregatedResult.

    Entered only when root_task.status == "accepted" (or "done").

    Uses read-only task tree inspection tools.
    Applies NodeRetryPolicy for LLM call failures.
    """

    def __init__(self, config: NodeConfig, tool_policy: NodeToolPolicy, retry_policy: NodeRetryPolicy):
        ...

    async def arun(self, node_input: NodeInputLike) -> AggregatedResult:
        """
        Perform guided BFS right-to-left traversal of the root task tree,
        consolidate results, and return AggregatedResult.
        """
        ...

    def on_complete(self) -> QueueAdvancement:
        """
        Returns QueueAdvancement to advance to the next node (ResponseNode).
        AggregatedResult is propagated to ResponseNode.
        """
        ...


class AggregatedResult:
    """
    Output model for result aggregation.
    root_task_id: str
    task_summaries: list[str]
    accepted_results: list[TaskResult]
    artifacts: list[dict]
    final_context: str
    response_continuation: str
    metadata: dict
    """
    pass
```

### Traversal Strategy Interface

```python
# Guided BFS helper (internal to ResultAggregationNode)
def _traverse_task_tree(root_task: Task) -> TraversalResult:
    """
    BFS right-to-left traversal starting from root task.
    For each visited task:
      - Collect task summary
      - Collect accepted TaskResult (if any)
      - Collect artifacts (if any)
      - Collect reviewer decision (if any)
    May stop early if sufficient context collected (configurable threshold).
    Returns consolidated intermediate data.
    """
    ...
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| No root task exists | `NodeExecutionError("No root task to aggregate")` | Invariant violation — should not be reachable |
| Root task not accepted/done | `NodeExecutionError("Root task not in accepted/done state")` | Invariant violation — loop must guard routing |
| LLM consolidation call fails | Retry via `NodeRetryPolicy`; `NodeExecutionError` if exhausted | Standard retry behavior |
| No accepted results found | `AggregatedResult` with empty lists, fallback in `final_context` | Not an error — valid state |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create `AggregatedResult` data model in `tinycua.models.aggregated_result`
- [ ] Implement `TinyCUAResultAggregationNode` with guided BFS right-to-left traversal
- [ ] Implement read-only task tree inspection using task interaction helpers
- [ ] Implement early termination threshold (configurable via `NodeConfig`)
- [ ] Wire `_on_reviewer_accept` in `TinyCUALoop` to route to ResultAggregationNode when root task is accepted/done
- [ ] Wire `on_complete` to advance queue to ResponseNode with `AggregatedResult` propagation
- [ ] Add unit tests for BFS traversal, early termination, and empty task tree
- [ ] Add integration tests for routing from root task acceptance → aggregation → response

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Support configurable aggregation strategies (e.g., different traversal orders, depth limits)
- [ ] Add serialization/deserialization for `AggregatedResult` for debugging/transcript export

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use guided BFS right-to-left / most-recent-first for task tree traversal.
   - **Reason**: Matches the target architecture design. Right-to-left BFS prioritizes the most recently created/modified tasks, which are likely the most relevant for response synthesis.
   - **Alternatives Considered**: DFS (pre-order) — rejected because it would visit oldest tasks first. Exhaustive BFS — rejected because selective traversal with early termination is more efficient.

2. **Decision**: Early termination threshold is configurable via `NodeConfig`.
   - **Reason**: Different use cases may need different amounts of context. Some sessions may want exhaustive aggregation; others may want quick responses with minimal context.
   - **Alternatives Considered**: Fixed threshold — rejected as too inflexible. No early termination — rejected for large task trees.

3. **Decision**: `AggregatedResult` is a standalone dataclass, not part of a larger propagation envelope.
   - **Reason**: Simplicity. The data model is self-contained and passed to ResponseNode via standard propagation.
   - **Alternatives Considered**: Embedding in `SessionContextEntry` — rejected because it's a different abstraction level.

4. **Decision**: ResultAggregationNode uses read-only tools for task inspection (no mutation).
   - **Reason**: Aggregation should be a side-effect-free operation. Task tree mutation is the responsibility of TaskAnalyzer and TinyCUALoop helpers.
   - **Alternatives Considered**: Allowing aggregation to prune/clean up the task tree — rejected as scope creep and violation of separation of concerns.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Large task tree causes excessive LLM calls or context | Med | High | Early termination threshold; configurable depth/token limits |
| BFS traversal order is incorrect for some task topologies | Low | Med | Unit tests with various tree shapes (deep, wide, unbalanced) |
| ResultAggregationNode is invoked before root task is accepted | Low | High | Tight guard in loop routing; defensive check in the node itself |
| AggregatedResult metadata grows unbounded | Low | Low | Metadata field is a freeform dict; document expected keys in design |

---

## Open Questions _(optional)_

1. **How does the loop determine "enough context" for early termination?**
   - Current thinking: Configurable threshold — either a count of tasks processed or a token budget for `final_context`. Default could be "process all top-level children".
   - Needs resolution during implementation.

2. **Should `AggregatedResult` include a `response_continuation` field at this stage, or is that strictly a ResponseNode concern?**
   - Current thinking: Include it with a default/empty value so ResponseNode receives the field. The field is part of the target architecture model.
   - The design follows the existing `AggregatedResult` model from the architecture doc.

---

## References

- Spec: `./spec.md`
- Target architecture: `src/tinycua/docs/design/loops/result_aggregation.md`
- Related designs: `src/tinycua/docs/design/loops/response.md`, `src/tinycua/docs/design/models/task.md`
- Existing spec example: `specs/tinycua-executor-reviewer/`
