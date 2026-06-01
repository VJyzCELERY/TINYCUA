# AgentGraph Queue System

> **File:** `docs/design/orchestration/graph_queue.md`
> **Package:** `tinycua.orchestration.graph_queue`
> **Last Updated:** 2026-06-02
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
  · item_id: str                         # runtime-only handle, regenerated on load
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

Runtime nodes and graphs also have auto-generated runtime handles:

```text
BaseAgentNode.node_id: str      # runtime-only, not persisted as state
AgentGraph.graph_id: str        # runtime-only, not persisted as state
GraphQueueItem.item_id: str     # runtime-only, not persisted as state
```

These IDs are convenience handles for logs, debugging, queue lookup, and pointing to a
live object when no stronger domain identifier is available. They are regenerated when
objects are constructed or hydrated. Durable references use `session_id`,
`AgentState.type`, `AgentKind`, and serialized queue metadata instead.

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

### Universal Lazy Loading Rule

Lazy loading is a universal graph rule: the queue may describe future work without
materializing the live Python object behind that work.

```text
Queue item descriptor only:
  · AgentKind / GraphKind / NodeFactory
  · session_id if an existing persisted session should be reused
  · input / terminal / session_policy metadata

Live object materialized only when needed:
  · queue item reaches index 0
  · graph resumes a running active item
  · explicit debugging/introspection asks for a live object
```

This prevents graph restore and routing from slowing down as the session tree grows.
Loading a root snapshot may deserialize the session tree, but it should not rebuild
every AgentNode, subgraph, SDK `Agent`, or tool wrapper unless that object is active or
explicitly requested.

When `session_policy="reuse"`, the queue item can hold a `session_id` without loading
the corresponding AgentNode immediately. On activation, the graph finds that session in
the loaded tree and calls `load_agent_node(session)` or constructs the subgraph with
`session=session`.

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

## Adding Nodes

Graphs should centralize queue insertion through `add_node()` instead of letting
callers build raw `GraphQueueItem` objects manually:

```text
AgentGraph.add_node(
    node_ref: AgentKind | NodeFactory | BaseAgentNode | AgentGraph,
    *,
    input: str | None = None,
    terminal: bool = False,
    session_policy: "lazy" | "reuse" = "lazy",
    placement: "tail" | "front" | "after_active" | "replace_tail" = "tail",
) -> GraphQueueItem
```

`add_node()` owns the insertion mechanics:

- assign a runtime-only `item_id`
- preserve lazy session creation when `node_ref` is an `AgentKind` or factory
- reuse an already-live node/subgraph when `node_ref` is an instance and
  `session_policy="reuse"`
- attach input and terminal metadata consistently
- perform the requested queue placement without exposing raw list mutation to route
  handlers

For example:

```text
self.add_node(AgentKind.INFORMATION_DIGESTER, input=payload, placement="after_active")
self.add_node(existing_worker, input=payload, session_policy="reuse", placement="replace_tail")
```

The lower-level mutation operations (`pop_active`, `replace_tail`, etc.) can still
exist, but route handlers should prefer `add_node()` so queue item construction,
runtime IDs, lazy creation, and reuse policy stay consistent.

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
| Central insertion API | `AgentGraph.add_node()` creates queue items | Keeps queue IDs, placement, lazy creation, and reuse policy consistent |
| Runtime IDs only | Node/graph/item IDs are regenerated handles | Lets logs and queue lookups point to live objects without becoming persisted state |
| Universal lazy loading | Queue descriptors are cheap; live nodes load on activation | Keeps restore/routing fast even with large session trees |

---

## Related

- [AgentGraph overview](overview.md)
- [TinyCUA queue usage](tinycua.md)
- [TinyCUAWorker queue usage](worker.md)
