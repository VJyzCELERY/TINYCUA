# TinyCUATaskExecutorNode

> **Package:** `tinycua.loops.task_executor`
> **Status:** Target architecture

## Role

`TinyCUATaskExecutorNode` is a concrete `ProcessNode` that performs ReAct-style
execution of the current active task. It is the only node that may execute task actions
and produce execution results.

## Non-Responsibilities

- Must not select the active task (active task selection belongs to TinyCUALoop / task
  helpers).
- Must not edit the active task or mutate the task tree.
- Does not review execution results (that belongs to ResultReviewer).
- Does not synthesize final user responses.

## Inputs

- `DigestedInformation` forwarded by upstream node (Worker or TaskAnalyzer).
- Current active task reference from TinyCUALoop / task helpers.
- High-level task tree list (read-only view).

## Outputs / State Produced

- Execution result for the current active task.
- May emit mandatory passthrough / HITL request if blocked.
- May use `enhanced_context_retrieval` if more information is needed.

## Tools

| Tool Scope | Description |
|------------|-------------|
| Active task execution tools | Execute the current active task and update task result. |
| `enhanced_context_retrieval` | Search scoped context for additional information when needed. |
| HITL / mandatory passthrough | Emit passthrough if blocked on user input. |

### Tool Restrictions

- cannot select active task (active task selection belongs to TinyCUALoop / task helpers).
- cannot edit active task or mutate the task tree.

## Queue Behavior / `on_complete()`

```text
TaskExecutor completes:
  → Advance queue; next node is ResultReviewer
```

TaskExecutor executes the active task and advances. ResultReviewer then evaluates the
execution result.

## Propagation

- Propagates execution result to ResultReviewer.

## Failure / Retry Behavior

Retry according to `NodeRetryPolicy`. Execution failure may trigger ResultReviewer
`retry` or `replan` decisions.

## Active Task Ownership

Active task ownership belongs to `TinyCUALoop` / task helpers, which store:
- The root task tree.
- Current active task reference/id.
- Task interaction helpers.

TaskExecutor receives the active task as input but must not mutate the active task
reference or task tree structure.

See the full handoff protocol in
[`../models/task.md`](../models/task.md#active-task-handoff-protocol).

## Related Config

- `NodeToolPolicy` — execution tool scope with tree mutation restrictions.
- `NodeRetryPolicy` — retry behavior.

## Related

- [`node.md`](node.md)
- [`../tools/task.md`](../tools/task.md)
- [`../models/task.md`](../models/task.md)
