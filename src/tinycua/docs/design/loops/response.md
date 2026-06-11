# TinyCUAResponseNode

> **Package:** `tinycua.loops.response`
> **Status:** Ready for Implementation

## Role

`TinyCUAResponseNode` is a concrete `ProcessNode` and the terminal/suspendable response
node. It steers final synthesis from prior node response/continuation input and produces
the user-facing answer. It is not a generic `PrimaryNode`.

## Non-Responsibilities

- Does not own detailed task traversal or task-tree search (that belongs to
  ResultAggregation and task helpers).
- Does not execute tasks.
- Does not review results.

## Inputs

- `AggregatedResult` from ResultAggregationNode.
- Accumulated root/session context.
- Latest propagated node output.
- Optional digested information from InformationDigesterNode.

## Outputs / State Produced

- Final user-facing response string.
- May maintain a session for audit/todo/tool execution.

## Tools

| Tool Scope | Description |
|------------|-------------|
| Information digestion request | May request InformationDigesterNode for additional context. |
| Direct tool access | May use allowed tools directly when context is insufficient. |

## LLM Input Construction

ResponseNode's LLM input is built primarily from:
1. Accumulated root/session_context.
2. Latest propagated node output.

It may maintain a session for audit/todo/tool execution, but its message policy treats
it as a continuation of the current TinyCUA session.

## Context Sufficiency Check

On every call, ResponseNode first analyzes whether available context is sufficient:

```text
ResponseNode enters:
  1. Analyze available context.
     → If sufficient: produce final answer.
     → If insufficient:
        a. Use allowed tools directly, OR
        b. Request InformationDigesterNode (if enabled).
```

## Queue Behavior / `on_complete()`

```text
ResponseNode completes:
  → Terminal node: queue processing ends.
  → Return final response string or stream events.

ResponseNode suspends for digestion:
  → suspend_current_and_prepend([InformationDigesterNode(parent=ResponseNode)])
  → Digester completes → ResponseNode resumes.
```

### Suspension and Resume

When ResponseNode suspends for information digestion:

1. Constructs `NodeInput(messages=[...], payloads=[...])` from selected
   `session_context` messages plus optional digest request payload.
2. Calls `queue.suspend_current_and_prepend([InformationDigesterNode(parent=response_node)])`.
3. Digester uses selected-output propagation targeting its parent session.
4. Digest lands in suspended ResponseNode's `session_context`.
5. ResponseNode resumes only after digest output has propagated back.

## Propagation

- This is the terminal node; no further queue propagation.
- Returns final response string to `TinyCUALoop`.

## Failure / Retry Behavior

Retry according to `NodeRetryPolicy`.

## Related Config

- `NodeToolPolicy` — information digestion and direct tool scope.
- `NodeRetryPolicy` — retry behavior.

## Related

- [`node.md`](node.md)
- [`node_queue.md`](node_queue.md)
- [`result_aggregation.md`](result_aggregation.md)
- [`information_digester.md`](information_digester.md)
