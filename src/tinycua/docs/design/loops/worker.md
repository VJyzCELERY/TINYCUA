# TinyCUAWorkerNode

> **Package:** `tinycua.loops.worker`
> **Status:** Target architecture

## Role

`TinyCUAWorkerNode` is a concrete `DecisionNode` that owns task planning and execution
orchestration. It replaces the old worker subgraph and worker QueryAnalyst input gate.
Worker is the decision hub for task creation, recreation, reanalysis, passthrough, and
execution advancement.

## Non-Responsibilities

- Does not create or mutate tasks directly (delegates to TaskCreate, TaskAnalyzer).
- Does not execute tasks (delegates to TaskExecutor).
- Does not review results (delegates to ResultReviewer).
- Does not synthesize final user responses (delegates to ResponseNode).

## Inputs

- `NodeInput` from QueryAnalyst, containing the original user query and session context.
- Continuation input from downstream nodes when re-entered.

## Outputs / State Produced

- `DecisionResult` with one of the indexed route labels.
- Preserves and passes through the original input query downstream; transformed/filter
  output may be added but must not replace the original query.

## Tools

| Tool Scope | Description |
|------------|-------------|
| Worker decision tools only | Worker uses its own decision/routing tools; it must not use task creation, analysis, or execution tools. |

## Route Labels

| Label | Behavior |
|-------|----------|
| `task_creation` | Deterministic first-time creation: no task exists yet. |
| `task_recreation` | Task exists and should be rebuilt/replaced. |
| `task_reanalysis` | Task exists and should be refined without full replacement. |
| `passthrough` | Forward input to an already active or queued worker-owned node/session. |
| `proceed_execution` | Edge case: task and active task exist but no executor is queued/active. |

## Two-Step Decision Process

Worker is a `DecisionNode` and uses the same two-step process as QueryAnalyst:

```text
analysis call → verdict/classification tool call → RouteMap dispatch
```

1. **Analysis call**: LLM call analyzes the current state (task existence, queue state).
2. **Verdict call**: A second LLM call must use the classification/verdict tool and
   choose from indexed labels.
3. **Dispatch**: `RouteMap` dispatches the validated label to the corresponding handler.

## Queue Behavior / `on_complete()`

```text
WorkerNode enters:
  1. Does task exist?
     ├── No → task_creation route
     └── Yes → continue

  2. Are worker-spawned nodes queued/active?
     ├── Yes → LLM decision with labels:
     │         task_recreation, task_reanalysis, passthrough, proceed_execution
     └── No → LLM decision without passthrough:
              task_recreation, task_reanalysis, proceed_execution
```

### Route Queue Shapes

```text
task_creation:
  [TaskCreateNode, TaskAnalyzerNode, AnalysisEffortNode, TaskExecutor, ResultReviewer, ResponseNode]

task_recreation:
  [TaskAnalyzerNode(+TaskInit/TaskCreate), AnalysisEffortNode, TaskExecutor, ResultReviewer, ResponseNode]

task_reanalysis:
  [TaskAnalyzerNode(no TaskInit/TaskCreate), AnalysisEffortNode, TaskExecutor, ResultReviewer, ResponseNode]

proceed_execution:
  [TaskExecutor, ResultReviewer, ResponseNode]
```

Passthrough advances the Worker and forwards input to the next worker-owned node.

## Propagation

- Preserves the original input query for downstream nodes.
- Optionally adds transformed/filter output but must not replace the original query.

## Failure / Retry Behavior

Invalid or missing route labels retry according to `NodeRetryPolicy`. Retry prompts
are assistant-role continuations.

## Related Config

- `NodeRetryPolicy` — retry behavior for invalid/missing labels.
- `WorkerEffort` — effort level configuration passed to AnalysisEffortNode.

## Related

- [`route_map.md`](route_map.md)
- [`node.md`](node.md)
- [`analysis_effort.md`](analysis_effort.md)
- [`../models/classification.md`](../models/classification.md)
