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
  · current → Node | None          # returns items[0] when present
  · advance() → Node | None          # propagates current session before removal
  · spawn_after_current(nodes) → None # keeps current session active
  · suspend_current_and_prepend(nodes) → None # preserves suspended node session
  · clear_after_current() → None     # drops queued nodes without mutating sessions
  · ensure_terminal(default_response_node) → None # guarantees terminal current path
  · is_empty() → bool
```

Operation side effects:

- `advance()` calls `propagate()` on `items[0]` if the node completed and has not already
  propagated, removes `items[0]`, and returns the new `current` node or `None`.
- `spawn_after_current(nodes)` inserts nodes after `items[0]`. It does not change
  `current`; the loop re-reads `queue.current` after `on_complete()`.
- `suspend_current_and_prepend(nodes)` keeps the current node queued, inserts the new
  nodes before it, and makes the first prepended node the new `current`.
- `clear_after_current()` removes nodes after `items[0]`; removed node sessions are not
  mutated, but no further propagation occurs unless it happened before removal.
- `ensure_terminal(default_response_node)` appends the default response node when the
  queue would otherwise have no terminal response path.

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
terminal path, `ensure_terminal(...)` MUST append a default response node.

## Related

- [`tinycua_loop.md`](tinycua_loop.md)
- [`propagation.md`](propagation.md)
