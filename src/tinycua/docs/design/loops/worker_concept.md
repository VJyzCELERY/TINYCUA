# TinyCUAWorkerNode

> **Package:** `tinycua.loops.worker`
> **Status:** Target architecture

## Role

`TinyCUAWorkerNode` is a concrete `DecisionNode`. It replaces the target role of the old
worker subgraph and worker QueryAnalyst input gate.

There is no separate Worker QueryAnalyst in the target architecture.

## Existing WorkerNode Reuse

When QueryAnalyst routes to worker, if an existing WorkerNode is already queued before the
terminal ResponseNode, do not spawn a new WorkerNode. Forward/assign the current NodeInput
to the existing WorkerNode. An existing WorkerNode counts as part of the worker-owned queue
segment for stale detection and clearing.

## Flow

```text
TinyCUAWorkerNode enters

1. Does task exist?
   ├── No
   │   → spawn TinyCUATaskAnalyzerNode with TaskInit/TaskCreate tools
   │   → WorkerNode calls `queue.advance()` and does not re-insert itself
   └── Yes
       → continue

2. Are worker-spawned nodes queued/active?
   ├── Yes
   │   → call Worker LLM decision with labels:
   │       task_recreation, task_reanalysis, passthrough, proceed_execution
   └── No
       → call Worker LLM decision without passthrough:
           task_recreation, task_reanalysis, proceed_execution
```

## Routes

| Route | Behavior |
|-------|----------|
| `task_recreation` | Clear worker-spawned nodes and spawn TaskAnalyzer with TaskInit/TaskCreate. |
| `task_reanalysis` | Clear worker-spawned nodes and spawn TaskAnalyzer without TaskInit/TaskCreate. |
| `passthrough` | WorkerNode calls `queue.advance()`, does not re-insert itself, and forwards input to the next worker-spawned node. |
| `proceed_execution` | Spawn/continue TaskExecutor and ResultReviewer path. |

Passthrough is only available when a worker-spawned node exists to receive it.

## Related

- [`route_map.md`](route_map.md)
- [`node.md`](node.md)
