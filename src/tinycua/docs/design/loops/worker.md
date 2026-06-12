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

- `DigestedInformation` from QueryAnalyst (via InformationDigesterNode spawned before
  Worker). Contains original query in fallback case, digested context in success case.
- Continuation input from downstream nodes when re-entered.

## Outputs / State Produced

- `DecisionResult` with one of the indexed route labels.
- `DigestedInformation` forwarded to downstream nodes as the node query.
- `WorkerDecision` used for routing only.

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

### Worker Reuse Queue Example

When QueryAnalyst routes to an existing WorkerNode and the Worker chooses
`task_recreation`, the queue transition is:

```text
Before (QueryAnalyst routes to existing WorkerNode):
  [QueryAnalyst, WorkerNode(reused), TaskExecutor(stale), ResultReviewer, ResponseNode]

QueryAnalyst spawns InformationDigester before Worker:
  [InformationDigesterNode(parent=WorkerNode), WorkerNode(reused), TaskExecutor(stale), ResultReviewer, ResponseNode]

InformationDigester completes, propagates to Worker session:
  [WorkerNode(current), TaskExecutor(stale), ResultReviewer, ResponseNode]

Worker chooses task_recreation:
  clear_after_current()
  -> [WorkerNode(current)]

Route handler inserts replacement path:
  [WorkerNode, TaskAnalyzerNode(+TaskInit/TaskCreate), AnalysisEffortNode,
   TaskExecutor, ResultReviewer, ResponseNode]
```

Any route handler that calls `clear_after_current()` MUST call
`queue.ensure_terminal(default_response_node)` before returning if the clear removed the
terminal response path. `ensure_terminal(...)` is the helper used by the route handler;
TinyCUALoop's run-entry bootstrap is only a fallback for run startup and recovery. This
guarantees the queue always has a valid terminal output node.

Passthrough advances the Worker and forwards input to the next worker-owned node.

## Propagation

- Forwards DigestedInformation (which contains the original query in fallback or
  digested context in success case) along with WorkerDecision to downstream nodes.
- WorkerDecision is used for routing only; DigestedInformation is the node query
  for spawned nodes.

## Transient Routing Node Behavior

Worker is a transient routing/continuation node. It receives context, decides
routing, and forwards selected output to the next node. It does not
backward-propagate its own output directly. Its output becomes durable when the
next node receives it as input and later propagates its own input segment upward.

```text
Worker -> TaskAnalyzerNode -> TaskExecutor

Worker forwards: [DigestedInformation, WorkerDecision]
TaskAnalyzer context: TaskAnalyzer prior + DigestedInformation + WorkerDecision + TaskAnalyzerOutput
TaskAnalyzer termination: parent gets TaskAnalyzer prior + DigestedInformation + WorkerDecision;
                          TaskExecutor gets TaskAnalyzerOutput
```

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
- [`information_digester.md`](information_digester.md)
- [`../models/classification.md`](../models/classification.md)
- [`../models/digested_information.md`](../models/digested_information.md)
