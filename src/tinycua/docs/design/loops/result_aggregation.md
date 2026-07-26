# TinyCUAResultAggregationNode

> **Package:** `tinycua.loops.result_aggregation`
> **Status:** Target architecture

## Role

`TinyCUAResultAggregationNode` is a concrete `ProcessNode` entered only after retained
work is terminal. It traverses the root task tree, inspects each task
context/result/artifacts/reviewer decisions, consolidates information, and emits
response-ready context for `ResponseNode`.

## Non-Responsibilities

- Does not execute tasks.
- Does not review results (that belongs to ResultReviewer).
- Does not synthesize final user-facing responses (that belongs to ResponseNode).

## Inputs

- Root task tree with all task results, artifacts, and reviewer decisions.
- Task interaction helpers for tree traversal.

## Outputs / State Produced

- `AggregatedResult` containing consolidated information for ResponseNode.

## Tools

| Tool Scope | Description |
|------------|-------------|
| Read-only task tree inspection | Traverse and inspect task tree nodes for aggregation. |

## AggregatedResult Model

```text
AggregatedResult
  · root_task_id: str
  · task_summaries: list[str]
  · accepted_results: list[TaskResult]
  · compromised_results: list[TaskResult]
  · artifacts: list[dict]
  · final_context: str
  · response_continuation: str
  · metadata: dict
```

Accepted outputs and compromised unsuccessful limitations remain separate. Compromised
summaries are labeled explicitly so ResponseNode cannot present them as verified results.

## Traversal Strategy

- **Starts at the root task.**
- **Guided BFS right-to-left / most-recent-first.**
- May select any task node for deeper inspection.
- Does not need to perform exhaustive BFS if enough response-ready context is found.
- Selective deeper reads instead of requiring exhaustive BFS.

## Queue Behavior / `on_complete()`

```text
ResultAggregationNode completes:
  → Advance queue; next node is ResponseNode
```

## Propagation

- Propagates `AggregatedResult` to ResponseNode for final synthesis.

## Failure / Retry Behavior

Retry according to `NodeRetryPolicy`.

## Related Config

- `NodeToolPolicy` — read-only task tree inspection scope.
- `NodeRetryPolicy` — retry behavior.

## Related

- [`node.md`](node.md)
- [`response.md`](response.md)
- [`../models/task.md`](../models/task.md)
