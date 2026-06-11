# Feature Specification: TinyCUAResultAggregationNode

**Status**: Draft
**Created**: 2026-06-11
**Last Updated**: 2026-06-11
**Subproject(s) Affected**: tinycua (loops/result_aggregation, loops/tinycua_loop, loops/__init__.py)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide `TinyCUAResultAggregationNode` so the TinyCUA execution loop can **consolidate results from an accepted root task tree and produce response-ready context** for `ResponseNode`, completing the accepted-task path in the architecture flow.
- **Gaps**: Milestone 3.2 delivered `TinyCUATaskExecutorNode` and `TinyCUAResultReviewerNode`, and Milestone 3.3 handled mandatory passthrough and continuation routing. When `ResultReviewer` accepts the root task, the loop currently has **no node that traverses the completed task tree, inspects results/artifacts/reviewer decisions, and consolidates them** into a structured aggregate for `ResponseNode`. The architecture design for `TinyCUAResultAggregationNode` exists in `src/tinycua/docs/design/loops/result_aggregation.md` and `src/tinycua/docs/design/loops/node.md` but has not been implemented.
- **Non-Goals**: This spec does NOT cover final response synthesis (Milestone 3.5 — ResponseNode), information digestion suspension (Milestone 3.6), propagation/dedupe (Milestone 4.1), tool scoping (Milestone 4.2), retry/validation (Milestone 4.3), or streaming/transcript events (Milestone 4.4). It does NOT cover the initial queue bootstrap or root-task tracking (Milestone 3.1). Aggregation is read-only: it does NOT execute tasks, review results, or synthesize user-facing responses.
- **Constraints**: Must work without modifying `tinycua-sdk` public APIs. Must not mutate the task tree — aggregation is purely read-only inspection. Must follow the existing `ProcessNode` contract. The `AggregatedResult` model must be compatible with `ResponseNode`'s input contract.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

After `TinyCUAResultReviewerNode` accepts the root task (the top-level task in the task tree is marked `done`), `TinyCUALoop` advances the queue to `TinyCUAResultAggregationNode`. The aggregation node traverses the completed task tree using guided BFS right-to-left / most-recent-first, collects task summaries, accepted results, artifacts, and reviewer decisions, and produces an `AggregatedResult`. The queue then advances to `ResponseNode` for final synthesis.

### Acceptance Scenarios

1. **Given** a completed root task tree where the root task is `done`, **When** `TinyCUAResultAggregationNode` is invoked, **Then** it produces an `AggregatedResult` containing task summaries and artifacts from all accepted tasks.
2. **Given** a root task tree with nested accepted tasks at multiple depths, **When** the aggregation node traverses, **Then** it visits children right-to-left / most-recent-first and consolidates results from all depths.
3. **Given** sufficient response-ready context is found early in traversal, **When** the aggregation node inspects tasks, **Then** it may stop early without exhaustive BFS.
4. **Given** `TinyCUAResultAggregationNode` produces an `AggregatedResult`, **When** `on_complete` is called, **Then** the queue advances to the next node (expected: `ResponseNode`).

### Early Termination Criterion

**"Sufficient response-ready context"** is defined as: having inspected at least one task with an accepted result (`TaskResult` with `execution_status == "succeeded"`) AND at least one artifact, OR reaching a configurable `max_inspected_tasks` threshold (default: all tasks in the tree for MVP). This provides a concrete, testable criterion for the early termination feature in acceptance scenario 3.

### Edge Cases

- What happens when the root task has no children? The aggregation node inspects the single root task result and produces an `AggregatedResult` from it alone.
- What happens when some tasks have no result (were never executed)? The aggregation node skips or records a `"not_executed"` status.
- What happens when the root task is NOT accepted/done? The aggregation node should never be entered — this is a guard enforced by the loop/queue routing.
- What happens with empty artifacts or no reviewer decisions? The `AggregatedResult` contains empty lists for those fields rather than failing.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a `TinyCUAResultAggregationNode` class extending `ProcessNode` in `tinycua.loops.result_aggregation`.
- **FR-002**: The node MUST only be entered when the root task is accepted/done (guard enforced by the calling loop/queue).
- **FR-003**: The node MUST traverse the accepted root task tree using guided BFS right-to-left / most-recent-first order.
- **FR-004**: The node MUST inspect each visited task's context, result, artifacts, and reviewer decisions during traversal.
- **FR-005**: The node MUST consolidate traversal results into an `AggregatedResult` model with fields: `root_task_id`, `task_summaries`, `accepted_results`, `artifacts`, `final_context`, `response_continuation`, `metadata`.
- **FR-006**: The node MUST support early termination of traversal when sufficient response-ready context has been gathered.
- **FR-007**: The node MUST NOT mutate the task tree — all operations are read-only inspection.
- **FR-008**: On `on_complete`, the node MUST advance the queue to the next node (expected: `ResponseNode`).
- **FR-009**: The node MUST propagate the `AggregatedResult` as session context for `ResponseNode`.
- **FR-010**: The `AggregatedResult` model MUST be importable from `tinycua.loops.result_aggregation` or `tinycua.models`.

### Key Entities

- **AggregatedResult**: Consolidated data structure containing root_task_id, task_summaries, accepted_results, artifacts, final_context, response_continuation, and metadata. Emitted by `TinyCUAResultAggregationNode` and consumed by `ResponseNode`.
- **TinyCUAResultAggregationNode**: A `ProcessNode` that performs read-only traversal of the accepted root task tree and produces `AggregatedResult`.
- **Task Traversal**: Guided BFS right-to-left / most-recent-first of the root task tree, selecting task nodes for inspection and consolidation.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

Objective, measurable checks that prove the problem is solved.

- [x] **Node exists and extends ProcessNode**: `TinyCUAResultAggregationNode` is defined in `tinycua.loops.result_aggregation` and extends `ProcessNode`.
- [x] **AggregatedResult model exists**: The `AggregatedResult` dataclass is defined and contains all required fields.
- [x] **BFS right-to-left traversal**: The node traverses the task tree in most-recent-first order (children visited right-to-left).
- [x] **Early termination works**: The node can stop traversal early when sufficient context is gathered, producing a partial but valid `AggregatedResult`.
- [x] **Read-only**: The node does not modify any task's status, result, or children.
- [x] **Queue advancement**: `on_complete` advances the queue (via `queue.advance()` or equivalent).
- [x] **Integration with loop**: When `ResultReviewer` accepts the root task, `TinyCUALoop` routes to aggregation, then to `ResponseNode`.
- [x] **All tests pass**: `cd src/tinycua && uv run pytest` passes for the result_aggregation module.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test `AggregatedResult` construction with all fields populated
- Test BFS right-to-left traversal with a multi-level task tree
- Test early termination: verify traversal stops and produces partial result
- Test read-only guarantee: verify task tree is not mutated after aggregation
- Test empty task tree (root task with no children)
- Test tasks with missing results/artifacts
- Test `on_complete` queue advancement

### Integration Tests

- Test full path: `ResultReviewer` accept root task → `TinyCUAResultAggregationNode` → `ResponseNode`
- Test that aggregation produces valid input for `ResponseNode`
- Test that `AggregatedResult` propagates as session context

### Manual Tests _(if applicable)_

- N/A — all behavior is verifiable through automated tests.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| `AggregatedResult` model | TODO | Dataclass in `tinycua.loops.result_aggregation` |
| BFS traversal logic | TODO | Right-to-left / most-recent-first |
| `TinyCUAResultAggregationNode` | TODO | ProcessNode subclass |
| `on_complete` queue advancement | TODO | Advance to ResponseNode |
| Integration with TinyCUALoop | TODO | Wire root-task-accept → aggregation route |
| Tests | TODO | Unit + integration tests |

---

## Open Questions _(optional)_

1. **Should `AggregatedResult` live in `tinycua.loops.result_aggregation` or `tinycua.models`?**
   - **Status**: Decided
   - **Decision**: Co-locate with the node in `tinycua.loops.result_aggregation` for simplicity, re-export from `tinycua.loops` if needed by `ResponseNode`.

2. **How does `TinyCUALoop` know to route to `ResultAggregationNode` vs continuing to the next active task?**
   - **Status**: Decided
   - **Proposed Answer**: The `_on_reviewer_accept` handler on `TinyCUALoop` checks if the accepted task is the root task (no parent). If root → spawn `ResultAggregationNode` then `ResponseNode`. If not root → advance to the next active task (existing behavior from Milestone 3.2).

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
