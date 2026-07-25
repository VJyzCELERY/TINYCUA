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
  · input_for_current() → NodeInputLike
  · advance() → Node | None          # propagates current session before removal
  · spawn_after_current(nodes) → None # keeps current session active
  · suspend_current_and_prepend(nodes) → None # preserves suspended node session
  · clear_after_current() → None     # drops queued nodes without mutating sessions
  · ensure_terminal(default_response_node) → None # guarantees terminal current path
  · is_empty() → bool
```

Operation side effects:

- `input_for_current()` returns the `NodeInputLike` assigned to `items[0]`. Entry nodes
  receive input derived from the root session and SDK-provided messages. Spawned or
  prepended nodes receive input assigned by the route handler or suspending parent.
- `advance()` calls `propagate()` on `items[0]` if the node completed and has not already
  propagated. Propagation follows the segmented context model: the node's prior+input
  segment propagates upward per `PropagationRule`, while the output segment is forwarded
  to the next node as `NodeInput`. After propagation, removes `items[0]` and returns
  the new `current` node or `None`.
- `advance()` rejects a successor with the same `node_id`. Same-node retries use recovery
  re-entry before `node.completed`; a successful completion always changes nodes or ends.
- `spawn_after_current(nodes)` inserts nodes after `items[0]`. It does not change
  `current`; the loop re-reads `queue.current` after `on_complete()`.
- `suspend_current_and_prepend(nodes)` keeps the current node queued, inserts the new
  nodes before it, and makes the first prepended node the new `current`.
- `clear_after_current()` removes nodes after `items[0]`; removed node sessions are not
  mutated, but no further propagation occurs unless it happened before removal.
- `ensure_terminal(default_response_node)` appends the default response node when the
  queue would otherwise have no terminal response path.

`Node.on_complete(queue, result)` owns queue transitions. It calls `advance()`,
`spawn_after_current(...)`, `suspend_current_and_prepend(...)`, or another queue mutation
when appropriate. `TinyCUALoop` does not call `advance()` separately after
`on_complete()`.

## Suspension and Prepend

A node is suspended when it remains queued but is no longer at `queue[0]`. No dedicated
persisted suspended state is required.

### ResponseNode Digester Pattern

```text
Before:
  [ResponseNode]

ResponseNode requests more information:
  [InformationDigesterNode(parent=ResponseNode), ResponseNode]

Digester completes:
  [ResponseNode]
```

The prepended node propagates selected output back to its parent before the parent
resumes.

## ResponseNode Digester Handoff

When `ResponseNode` suspends itself for information digestion:

1. The response node constructs `NodeInput(messages=[...], payloads=[...])` from a copy of
   selected `response_node.session.session_context` messages plus an optional digest
   request payload.
2. It calls `queue.suspend_current_and_prepend([InformationDigesterNode(parent=response_node)])`
   and assigns that `NodeInput` to the prepended digester node.
3. The digester may read the copied input messages and retrieval tools, but it does not
   re-store the copied messages in its own reusable context.
4. The digester uses a selected-output propagation rule targeting its parent session; the
   digest lands in the suspended response node's `session_context`.
5. The response node resumes only after the digest output has propagated back.

## Terminal Handling

`TinyCUAResponseNode` is the usual terminal response node. If the queue loses its
terminal path, `ensure_terminal(...)` MUST append a default response node.

## Queue Bootstrap

Every `TinyCUALoop.run(...)` enforces these invariants:

1. Prepend or ensure `TinyCUAQueryAnalystNode` as the run entry node.
   - If `QueryAnalyst` is already current from an interrupted run, do not duplicate it.
2. Ensure a terminal node exists at the end of the queue.
   - If an existing terminal path exists, do nothing.
   - If no terminal path exists, append default `TinyCUAResponseNode`.

This ensures predictable queue state for crash recovery, HITL continuation, stale queue
recovery, and terminal safety.

## Related

- [`tinycua_loop.md`](tinycua_loop.md)
- [`propagation.md`](propagation.md)
