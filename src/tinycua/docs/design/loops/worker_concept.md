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
   ├── No → task_creation route (see Routes)
   └── Yes → continue

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
| `task_creation` | Deterministic first-time creation: spawn TinyCUATaskCreateNode to create root task, then TaskAnalyzerNode (without TaskInit/TaskCreate tools), then AnalysisEffortNode. |
| `task_recreation` | Clear worker-spawned nodes; spawn TaskAnalyzerNode with TaskInit/TaskCreate tools (LLM-assisted), then AnalysisEffortNode. |
| `task_reanalysis` | Clear worker-spawned nodes; spawn TaskAnalyzerNode without TaskInit/TaskCreate tools, then AnalysisEffortNode. |
| `passthrough` | WorkerNode calls `queue.advance()`, does not re-insert itself, and forwards input to the next worker-spawned node. |
| `proceed_execution` | Spawn/continue TaskExecutor and ResultReviewer path. |

Passthrough is only available when a worker-spawned node exists to receive it.

## Worker Planning Queue Shape

```text
task_creation:
  [TaskCreateNode, TaskAnalyzerNode, AnalysisEffortNode, TaskExecutor, ResultReviewer, ResponseNode]

task_recreation:
  [TaskAnalyzerNode(+TaskInit/TaskCreate), AnalysisEffortNode, TaskExecutor, ResultReviewer, ResponseNode]

task_reanalysis:
  [TaskAnalyzerNode(no TaskInit/TaskCreate), AnalysisEffortNode, TaskExecutor, ResultReviewer, ResponseNode]
```

`AnalysisEffortNode` is always inserted after the initial `TaskCreate` or `TaskAnalyzer`
pass and controls how many additional `[TaskAssessor, TaskAnalyzer]` rounds precede
execution. See [`analysis_effort.md`](analysis_effort.md) for the effort-gated loop
contract.

## Related

- [`route_map.md`](route_map.md)
- [`node.md`](node.md)
