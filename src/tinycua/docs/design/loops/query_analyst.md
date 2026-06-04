# TinyCUAQueryAnalystNode

> **Package:** `tinycua.loops.query_analyst`
> **Status:** Target architecture

## Role

`TinyCUAQueryAnalystNode` is a concrete `DecisionNode` and the top-level entrypoint for
every `TinyCUALoop.run(...)`. It classifies user input and routes the queue to the
appropriate downstream path. It is always the first node in the queue and may be re-entered
after user continuation.

## Non-Responsibilities

- Does not plan, decompose, or execute tasks.
- Does not own worker-owned nodes or task tree state.
- Does not synthesize final user-facing responses.

## Inputs

- `NodeInput` derived from root session context and SDK-provided messages.
- User continuation messages routed back via `mandatory_passthrough`.

## Context Assembly (Transient)

QueryAnalyst assembles a broad transient reasoning window for LLM input. This
assembled window is ephemeral and must not be backward-propagated wholesale.

```text
QueryAnalyst LLM input window (transient):
  root.session_context
  + active/queued node contexts by priority, e.g. Node3 -> Node2 -> Node1
  + current user query

QueryAnalyst forwarded output (durable):
  user_query
  + QueryAnalystResponse / continuation prompt
```

The assembled prompt window is used only for the current LLM classification call.
QueryAnalyst does not commit the entire assembled window to parent/root. Its output
is forwarded to the next node as `NodeInput` and becomes parent-visible when that
next node propagates its input segment upward per the segmented context model.

## Outputs / State Produced

- `DecisionResult` with one of the indexed route labels.
- Propagates original input query for downstream nodes; may add transformed/filter
  output but must not replace the original query.

## Tools

| Tool Scope | Description |
|------------|-------------|
| Read-only task inspection | QueryAnalyst may inspect existing task state for routing decisions, but must not mutate tasks. |

## Route Labels

| Label | Behavior |
|-------|----------|
| `worker` | Route to `TinyCUAWorkerNode` for task planning/execution. |
| `uncertain` | QueryAnalyst remains active and waits for user continuation. |
| `passthrough` | Forward user input to an already active or queued node/session. |

QueryAnalyst routes `worker | uncertain | passthrough`.

## Two-Step Decision Process

All `DecisionNode` classes, including QueryAnalyst, use a two-step process:

```text
analysis call → verdict/classification tool call → RouteMap dispatch
```

1. **Analysis call**: LLM call analyzes the user request.
2. **Verdict call**: A second LLM call must use the classification/verdict tool and
   choose from indexed labels. The latest valid verdict tool call determines the route
   label.
3. **Dispatch**: `RouteMap` dispatches the validated label to the corresponding handler.

Invalid or missing labels retry according to `NodeRetryPolicy`.

## Queue Behavior / `on_complete()`

```text
QueryAnalyst enters:
  1. Check for valid mandatory_passthrough.
     → If exists, forward continuation to target node/session.
  2. Otherwise, run normal classification.
     → worker: spawn WorkerNode (or forward to existing WorkerNode)
     → uncertain: QueryAnalyst remains active; waits for user continuation
     → passthrough: forward to target node/session
```

### Worker-Route Rule

When routing to `worker`:
- If an existing `WorkerNode` is already queued before the terminal `ResponseNode`,
  do not spawn a new `WorkerNode`. Forward/assign the current `NodeInput` to the
  existing `WorkerNode`.
- If no `WorkerNode` exists, spawn a new `WorkerNode` before the terminal `ResponseNode`.

### QueryAnalyst Deduplication

QueryAnalyst should only be spawned when no active QueryAnalyst exists. If another
QueryAnalyst is already active at the start, the new entry should emit/trigger mandatory
passthrough to the active QueryAnalyst rather than duplicating it.

## Propagation

- Preserves the original input query for downstream nodes.
- Optionally adds transformed/filter output but must not replace the original query.
- As a transient routing node, QueryAnalyst does not backward-propagate its assembled
  context window. Its output becomes durable through the next node's input propagation.

## Transient Routing Node Behavior

QueryAnalyst is a transient routing/continuation node. It assembles context for
reasoning, forwards selected output to the next node, and does not
backward-propagate its own output directly. Its output becomes durable when the
next node receives it as input and later propagates its own input segment upward.

```text
QueryAnalyst -> Node1 -> Node2

QueryAnalyst forwards: [user_query, QueryAnalystResponse]
Node1 context: Node1 prior + user_query + QueryAnalystResponse + Node1Output
Node1 termination: parent gets Node1 prior + user_query + QueryAnalystResponse;
                   Node2 gets Node1Output
```

## Failure / Retry Behavior

Invalid or missing route labels retry according to `NodeRetryPolicy`. Retry prompts
are assistant-role continuations.

## Related Config

- `NodeRetryPolicy` — retry behavior for invalid/missing labels.
- `NodeToolPolicy` — read-only task inspection scope.

## Related

- [`route_map.md`](route_map.md)
- [`node.md`](node.md)
- [`worker_concept.md`](worker_concept.md)
- [`../models/classification.md`](../models/classification.md)
