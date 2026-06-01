# AgentGraph Queue System

> **File:** `docs/design/orchestration/graph_queue.md`
> **Package:** `tinycua.orchestration.graph_queue`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

The AgentGraph queue is the graph-level execution state. It preserves the graph's
shape, makes the active node unambiguous, and prevents limbo states where the runtime
does not know which node should receive the next action.

The graph does not ask AgentNodes to route themselves. An AgentNode runs, writes its
own `session.agent_state`, returns control to the graph, and the graph mutates the
queue to decide what happens next.

---

## Queue Contract

```text
GraphQueue
  · items: list[GraphQueueItem]

GraphQueueItem
  · node_ref: NodeRef | NodeFactory | AgentGraph
  · terminal: bool = False
  · input: str | None = None
  · session_policy: "lazy" | "reuse" = "lazy"
```

The active node is always:

```text
active_node = queue.items[0] if queue.items else None
```

If `active_node` is itself an `AgentGraph`, the parent graph treats that subgraph as a
single active node. The parent does **not** inspect or depend on the subgraph's internal
queue. For example, TinyCUA only knows `TinyCUAWorker` is active; it does not know
whether the worker is internally running TaskExecutor, ResultReviewer, or TaskAnalyzer.

---

## Lazy Session Creation

Adding a node to the queue does not create that node's `Session`.

```text
queue = [QueryAnalyst, InformationDigester, TinyCUAWorker]

# Only QueryAnalyst is first, so only QueryAnalyst exists or is created now.
# InformationDigester and TinyCUAWorker are scheduled shape, not live sessions yet.
```

A queued AgentNode creates or attaches its session only when it becomes index `0` and
the graph calls `node.run(query)`. This keeps queued graph shape cheap and avoids
creating sessions for branches that may be reprioritized or removed before execution.

---

## Graph-Owned Routing

The graph is the only layer that mutates queue order:

```text
run_active():
  item = queue[0]
  result = item.node.run(item.input)
  state = item.node.session.agent_state or graph_result
  graph_policy_applies(state)
```

Allowed graph mutations:

| Operation | Meaning |
|-----------|---------|
| `pop_active()` | Active node completed and the next queued node should run |
| `insert_after_active(item)` | Schedule a high-priority next node without losing current active result handling |
| `replace_tail(items)` | Replace all future work after the active node |
| `clear()` | Finish or cancel graph work |
| `clear_after_terminal()` | Terminal node completed; discard any remaining scheduled work |

AgentNodes never call these operations directly. They only return state.

---

## Terminal Nodes

A graph is truly done when its queue is empty or when a terminal node completes and the
graph clears the remaining tail.

For TinyCUA, `PrimaryAgentNode` is terminal: once it produces the externally visible
answer, TinyCUA should not continue to queued digester/worker work for that same user
query.

```text
[QueryAnalyst, InformationDigester, TinyCUAWorker]
  QueryAnalyst says passthrough
  → insert PrimaryAgentNode(terminal=True) after QueryAnalyst
  → PrimaryAgentNode completes
  → clear queued InformationDigester/TinyCUAWorker tail
  → TinyCUA run is done
```

---

## Input Gate With Existing Active Node

External user input can temporarily prepend an InputGate while preserving the previous
active node behind it:

```text
Before new input: [TinyCUAWorker]
New user query: prepend QueryAnalyst
During gate:      [QueryAnalyst, TinyCUAWorker]
```

When `QueryAnalyst` finishes, the graph can inspect the next queued item and decide:

- passthrough to the existing `TinyCUAWorker`
- insert `InformationDigester` before the worker
- replace the tail with `PrimaryAgentNode(terminal=True)`

The QueryAnalyst does not need to know the worker's internal active child. It only sees
the graph-level active node as `TinyCUAWorker`.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Active node | First queue item | O(1), unambiguous active-node lookup |
| Shape retention | Queue can contain future nodes before sessions exist | Graph shape survives reprioritization without eager node/session creation |
| Subgraph opacity | Parent sees subgraph as one queue item | Encapsulates nested worker state and queues |
| Routing owner | Graph mutates queue after node result | Prevents nodes from implicitly routing or creating limbo states |
| Terminal output | Terminal node completion clears tail | Prevents accidental work after final user-facing response |

---

## Related

- [AgentGraph overview](overview.md)
- [TinyCUA queue usage](tinycua.md)
- [TinyCUAWorker queue usage](worker.md)
