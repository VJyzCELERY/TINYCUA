# TinyCUATaskCreateNode

> **Package:** `tinycua.loops.task_create`
> **Status:** Target architecture

## Role

`TinyCUATaskCreateNode` is a concrete `ProcessNode` that performs first-time
deterministic root task creation. It is entered only after Worker chooses
`task_creation` and creates the root task before any analysis or decomposition begins.

## Non-Responsibilities

- Does not decompose the task tree beyond root creation.
- Does not perform analysis, assessment, or execution.
- Does not create subtasks or modify the task tree after initial creation.

## Inputs

- `DigestedInformation` forwarded by Worker (contains original query in fallback
  or digested context in success case).
- Chat history and selected session context (with dedupe to avoid duplicating entry
  context).

## Outputs / State Produced

- Root task created deterministically/tightly before analysis begins.
- Final response is treated as a summary of what it created, so the next node can use it
  as continuation/input context.

## Tools

| Tool Scope | Description |
|------------|-------------|
| TaskInit / TaskCreate only | Deterministic root task creation tools. Must not use analysis or decomposition tools. |

## Queue Behavior / `on_complete()`

```text
TaskCreateNode completes:
  → Advance queue; next node is TaskAnalyzerNode (without TaskInit/TaskCreate tools)
```

TaskCreateNode creates the root task and advances. The subsequent TaskAnalyzer runs
after root creation without TaskInit/TaskCreate authority.

## Propagation

- Propagates chat history and selected session context like other nodes, with dedupe
  to avoid duplicating entry context.
- Its final response is treated as a summary of what it created.

## Failure / Retry Behavior

Retry according to `NodeRetryPolicy`. Task creation failure prevents downstream nodes
from receiving a valid task tree.

## Related Config

- `NodeToolPolicy` — TaskInit/TaskCreate scope.
- `NodeRetryPolicy` — retry behavior.

## Related

- [`worker.md`](worker.md)
- [`node.md`](node.md)
- [`../tools/task.md`](../tools/task.md)
