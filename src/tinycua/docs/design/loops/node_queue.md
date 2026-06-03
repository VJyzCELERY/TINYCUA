# NodeQueue

> **Package:** `tinycua.loops.node_queue`
> **Status:** Target architecture

## Role

`NodeQueue` is the sequential execution structure inside `TinyCUALoop`. The active node
is always `queue[0]`. Queue position controls execution order; it does not imply
automatic context sharing.

```text
NodeQueue
  · items: list[Node]
  · current → Node | None
  · advance() → None
  · spawn_after_current(nodes) → None
  · suspend_current_and_prepend(nodes) → None
  · clear_after_current() → None
  · ensure_terminal(default_response_node) → None
  · is_empty() → bool
```

## Suspension and Prepend

A node is suspended when it remains queued but is no longer at `queue[0]`. No dedicated
persisted suspended state is required.

```text
Before:
  [TinyCUAResponseNode]

ResponseNode requests more information:
  [TinyCUAInformationDigesterNode(parent=TinyCUAResponseNode), TinyCUAResponseNode]

Digester completes:
  [TinyCUAResponseNode]
```

The prepended node propagates selected output back to its parent before the parent
resumes.

## Terminal Handling

`TinyCUAResponseNode` is the usual terminal response node. If the queue loses its
terminal path, `ensure_terminal(...)` may append a default response node.

## Related

- [`tinycua_loop.md`](tinycua_loop.md)
- [`propagation.md`](propagation.md)
