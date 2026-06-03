# TinyCUAWorkerNode

> **Package:** `tinycua.loops.worker`
> **Status:** Target architecture

## Role

`TinyCUAWorkerNode` is a concrete `DecisionNode`. It replaces the target role of the old
worker subgraph and worker QueryAnalyst input gate.

There is no separate Worker QueryAnalyst in the target architecture.

## Flow

```text
TinyCUAWorkerNode enters

1. Does task exist?
   ├── No
   │   → spawn TinyCUATaskAnalyzerNode with TaskInit/TaskCreate tools
   │   → terminate WorkerNode
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
| `passthrough` | Terminate WorkerNode and forward input to the next worker-spawned node. |
| `proceed_execution` | Spawn/continue TaskExecutor and ResultReviewer path. |

Passthrough is only available when a worker-spawned node exists to receive it.

## Related

- [`route_map.md`](route_map.md)
- [`node.md`](node.md)
