# Feature Specification: TinyCUAResultAggregationNode

**Status**: Draft
**Created**: 2026-06-11
**Last Updated**: 2026-06-11
**Subproject(s) Affected**: tinycua (loops/result_aggregation, loops/tinycua_loop)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide `TinyCUAResultAggregationNode` so the TinyCUA execution loop can **traverse the accepted root task tree, consolidate task context/results/artifacts/reviewer decisions, and emit an `AggregatedResult`** that provides response-ready context for `TinyCUAResponseNode`.
- **Gaps**: Milestone 3.2 delivered the TaskExecutor and ResultReviewer nodes, and Milestone 3.3 delivered mandatory passthrough and continuation routing. However, when a root task is accepted/done, there is no node that consolidates the full task tree's results before final response synthesis. The loop currently has no path from "root task accepted" to "response-ready context." Without ResultAggregationNode, ResponseNode has no structured aggregation of all task work products to synthesize from.
- **Non-Goals**: This spec does NOT cover final response synthesis (ResponseNode — Milestone 3.5), ResponseNode information-digestion suspension path (Milestone 3.6), propagation/dedupe (Milestone 4.1), tool scoping (Milestone 4.2), or streaming (Milestone 4.4). It does NOT cover changes to task execution or result review. It does NOT cover the BFS traversal algorithm implementation details — only the behavioral contract.
- **Constraints**: Must work without modifying `tinycua-sdk` public APIs. Must preserve the existing architecture design at `src/tinycua/docs/design/loops/result_aggregation.md`. The node must be entered only after the root task is accepted/done. The node uses read-only task tree inspection tools — it must NOT mutate the task tree.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

After the TaskExecutor/ResultReviewer cycle accepts the root task (all subtasks complete, root task marked done), the execution loop routes to ResultAggregationNode. The node traverses the root task tree using guided BFS right-to-left / most-recent-first, inspecting each task's context, results, artifacts, and reviewer decisions. It consolidates this information into an `AggregatedResult` and passes it to ResponseNode for final synthesis.

### Acceptance Scenarios

1. **Given** a root task with `status="accepted"` and multiple completed child tasks, **When** ResultAggregationNode is invoked, **Then** it traverses the task tree and produces an `AggregatedResult` containing task summaries, accepted results, artifacts, and final context.
2. **Given** an `AggregatedResult` is produced, **When** the node completes, **Then** the queue advances to ResponseNode with the aggregated context available for synthesis.
3. **Given** a task tree with only a root task (no children), **When** ResultAggregationNode is invoked, **Then** it produces an `AggregatedResult` with just the root task's context.
4. **Given** the BFS traversal encounters a task with no accepted result, **When** inspecting that task, **Then** it is skipped (only accepted/done tasks with results are included in the aggregation).
5. **Given** a very deep task tree with many nodes, **When** the BFS traversal finds sufficient response-ready context early, **Then** it may stop early without exhaustive traversal.

### Edge Cases

- What happens when ResultAggregationNode is invoked but no root task exists? The node raises a `NodeExecutionError`.
- What happens when the root task is not yet accepted/done? The node should be unreachable — the loop must guard against invoking aggregation before root task acceptance.
- What happens when no tasks have accepted results? The `AggregatedResult` contains empty lists for `accepted_results` and `task_summaries`, but `final_context` still contains a fallback indicating no results were aggregated.
- What happens when a child task has artifacts but no reviewer decision recorded? Artifacts are still included; missing reviewer decisions are recorded as unknowns in the metadata.
- What happens when the LLM call for consolidation fails? Standard `NodeRetryPolicy` handles retry; if exhausted, `NodeExecutionError` is raised.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: ResultAggregationNode MUST be enterable only when the root task is accepted/done.
- **FR-002**: ResultAggregationNode MUST perform a guided BFS right-to-left / most-recent-first traversal of the root task tree.
- **FR-003**: ResultAggregationNode MUST consolidate the following per-task: context, results, artifacts, and reviewer decisions.
- **FR-004**: ResultAggregationNode MUST emit an `AggregatedResult` containing `root_task_id`, `task_summaries`, `accepted_results`, `artifacts`, `final_context`, `response_continuation`, and `metadata`.
- **FR-005**: ResultAggregationNode MUST pass the `AggregatedResult` as response-ready context to ResponseNode.
- **FR-006**: ResultAggregationNode MAY stop traversal early if sufficient response-ready context has been collected.
- **FR-007**: ResultAggregationNode MUST use read-only task tree inspection tools — it MUST NOT mutate the task tree.
- **FR-008**: ResultAggregationNode MUST propagate the aggregated result to the next node (ResponseNode) via standard propagation mechanisms.

### Key Entities

- **AggregatedResult**: The output model containing consolidated information from the task tree traversal. Includes `root_task_id`, `task_summaries`, `accepted_results`, `artifacts`, `final_context`, `response_continuation`, and `metadata`.
- **TinyCUAResultAggregationNode**: A concrete `ProcessNode` that performs the task tree traversal and aggregation. Uses read-only tools for task tree inspection. Emits `AggregatedResult` on completion.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Root task acceptance triggers aggregation**: When root task is accepted/done, the loop routes to ResultAggregationNode, not directly to ResponseNode.
- [ ] **BFS traversal works**: The node traverses the task tree right-to-left / most-recent-first and collects task data.
- [ ] **AggregatedResult produced**: The node emits a valid `AggregatedResult` with all required fields populated.
- [ ] **ResponseNode receives context**: After aggregation completes, ResponseNode receives the `AggregatedResult` as context for synthesis.
- [ ] **No task tree mutation**: The node uses only read-only inspection tools and does not modify the task tree.
- [ ] **Early termination works**: With a large task tree, the node can stop early once sufficient context is found.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test that `TinyCUAResultAggregationNode` is a `ProcessNode` subclass.
- Test that `AggregatedResult` dataclass can be constructed with all fields.
- Test that BFS traversal visits children right-to-left / most-recent-first.
- Test that tasks without accepted results are skipped during traversal.
- Test early termination when sufficient context is collected.
- Test that `NodeRetryPolicy` is applied to the node's LLM calls.

### Integration Tests

- Test that when root task is accepted, the loop routes to ResultAggregationNode.
- Test that ResultAggregationNode completion advances the queue to ResponseNode.
- Test that `AggregatedResult` is propagated to ResponseNode.
- Test a multi-level task tree where aggregation produces correct consolidated output.
- Test that invoking ResultAggregationNode without an accepted root task raises an error.

### Manual Tests _(if applicable)_

- Run the full loop with a multi-task scenario and verify the final response contains aggregated context from all subtasks.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Spec | Draft | Initial version from roadmap + architecture doc |

---

## Open Questions _(optional)_

1. **What is the exact threshold for "enough response-ready context" for early termination?**
   - **Owner**: TBD
   - **Target**: During design phase
   - **Status**: Discussion
   - **Proposed Answer**: Configurable via node config; default could be "all top-level children collected" or a token budget for `final_context`.

2. **Does AggregatedResult need a serialization method for debugging/transcript recording?**
   - **Owner**: TBD
   - **Target**: During design phase
   - **Status**: Discussion
   - **Proposed Answer**: Likely yes — serialize to dict for propagation metadata.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
