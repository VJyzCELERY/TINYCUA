# Design Document: NodeQueue Basic Execution and Terminal Safety

**Spec**: `./spec.md`
**Status**: Approved
**Last Updated**: 2026-06-07

---

## Overview

This design replaces the M1.1 `NodeQueue` stub with a functional sequential execution structure that supports `advance()`, `spawn_after_current()`, `clear_after_current()`, and `ensure_terminal()`. The queue maintains a `list[Node]` as its backing store, tracks per-node `NodeInputLike` via a dict mapping, and enforces terminal safety through `ensure_terminal()` at queue bootstrap time. Suspension/prepend semantics are deferred to Milestone 1.7.

---

## Architecture

### Component Overview

```
NodeQueue
  · items: list[Node]
  · _inputs: dict[str, NodeInputLike]    # node_id → input mapping
  · current → Node | None                 # returns items[0] when present
  · input_for_current() → NodeInputLike
  · advance() → Node | None              # propagates current, removes items[0]
  · spawn_after_current(nodes) → None    # inserts after items[0]
  · clear_after_current() → None         # drops queued nodes after items[0]
  · ensure_terminal(default) → None      # appends terminal if missing
  · is_empty() → bool
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/loops/node_queue.py` | Modified | Replace M1.1 stub with full implementation |
| `tinycua/loops/node.py` | Referenced | `Node.is_terminal`, `Node.propagate()`, `Node.on_complete()` |
| `tinycua/loops/tinycua_loop.py` | Modified (future) | Will call `ensure_terminal()` at bootstrap (Milestone 1.6 integration) |

---

## Data Model

### NodeQueue

```python
@dataclass
class NodeQueue:
    """Sequential execution queue for TinyCUA nodes.

    Attributes:
        items: List of queued nodes. items[0] is always the active node.
        _inputs: Internal mapping of node_id to NodeInputLike for input tracking.
    """

    items: list[Node] = field(default_factory=list)
    _inputs: dict[str, NodeInputLike] = field(default_factory=dict)

    @property
    def current(self) -> Node | None:
        """Return the active node (items[0]) or None if empty."""
        return self.items[0] if self.items else None

    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return len(self.items) == 0

    def input_for_current(self) -> NodeInputLike:
        """Get input data for the current node."""
        if not self.items:
            return {}
        return self._inputs.get(self.items[0].node_id, {})

    def set_input(self, node: Node, input_data: NodeInputLike) -> None:
        """Set input data for a specific node."""
        self._inputs[node.node_id] = input_data

    def advance(self) -> Node | None:
        """Advance to the next node.

        Raises ValueError if the queue is already empty (FR-010).
        If the queue has nodes, calls propagate() on items[0] (if not already
        propagated), removes items[0], and returns the new current node — or
        None if the queue is now empty (FR-005).
        """
        if not self.items:
            raise ValueError("Cannot advance an empty queue")

        current_node = self.items[0]
        if not getattr(current_node, "_propagated", False):
            current_node.propagate()
        self.items.pop(0)
        self._inputs.pop(current_node.node_id, None)
        return self.current

    def spawn_after_current(self, nodes: list[Node]) -> None:
        """Insert nodes after the current node.

        Does not change current; the loop re-reads queue.current after on_complete().
        Raises ValueError if queue is empty. Calling with an empty list is a no-op.
        """
        if not self.items:
            raise ValueError("Cannot spawn after an empty queue")

        self.items[1:1] = nodes

    def clear_after_current(self) -> None:
        """Remove all nodes after the current node.

        Removed node sessions are not mutated, but no further propagation
        occurs unless it happened before removal.
        """
        if not self.items:
            return

        removed_nodes = self.items[1:]
        self.items = self.items[:1]
        for node in removed_nodes:
            self._inputs.pop(node.node_id, None)

    def ensure_terminal(self, default_terminal_node: Node) -> None:
        """Append a terminal node if none exists at the end of the queue.

        Checks if the last node in the queue has is_terminal=True.
        If not, appends the default_terminal_node.
        """
        if not self.items:
            self.items.append(default_terminal_node)
            return

        last_node = self.items[-1]
        if not last_node.is_terminal:
            self.items.append(default_terminal_node)
```

---

## API / Interface Contracts

### NodeQueue Contract

```python
class NodeQueue:
    """Sequential execution queue for TinyCUA nodes."""

    @property
    def current(self) -> Node | None:
        """Return the active node (items[0]) or None if empty."""

    def is_empty(self) -> bool:
        """Check if the queue is empty."""

    def input_for_current(self) -> NodeInputLike:
        """Get input data for the current node."""

    def set_input(self, node: Node, input_data: NodeInputLike) -> None:
        """Set input data for a specific node."""

    def advance(self) -> Node | None:
        """Advance to the next node.

        Raises ValueError if the queue is already empty (FR-010).
        If the queue has nodes, calls propagate() on items[0] (if not already
        propagated), removes items[0], and returns the new current node — or
        None if the queue is now empty (FR-005).
        """

    def spawn_after_current(self, nodes: list[Node]) -> None:
        """Insert nodes after the current node.

        Does not change current.
        Raises ValueError if queue is empty.
        No-op when called with an empty list.
        """

    def clear_after_current(self) -> None:
        """Remove all nodes after the current node.

        No-op if queue is empty or has only one node.
        """

    def ensure_terminal(self, default_terminal_node: Node) -> None:
        """Append terminal node if none exists at the end.

        Appends if last node is not terminal or queue is empty.
        """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `advance()` on empty queue | `ValueError("Cannot advance an empty queue")` | Prevents invalid state transition |
| `spawn_after_current()` on empty queue | `ValueError("Cannot spawn after an empty queue")` | No current node to spawn after |
| `spawn_after_current([])` with empty list | No-op | Consistent with Python slice assignment behavior |
| `clear_after_current()` on empty queue | No-op | Graceful handling |
| `ensure_terminal()` on empty queue | Appends default terminal | Ensures queue has terminal path |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Replace M1.1 `NodeQueue` stub with full implementation
- [ ] Implement `current` property returning `items[0]` or `None`
- [ ] Implement `is_empty()` method
- [ ] Implement `input_for_current()` with internal `_inputs` dict mapping
- [ ] Implement `set_input(node, input_data)` for input tracking
- [ ] Implement `advance()` with propagation call and empty queue safety
- [ ] Implement `spawn_after_current(nodes)` with empty queue safety
- [ ] Implement `clear_after_current()` with graceful empty handling
- [ ] Implement `ensure_terminal(default_terminal_node)` with terminal detection
- [ ] Update `TinyCUALoop.run()` to call `ensure_terminal()` at bootstrap
- [ ] Write comprehensive unit tests for all methods

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- None for this milestone. Suspension/prepend is deferred to Milestone 1.7.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use a dict mapping `_inputs: dict[str, NodeInputLike]` for input tracking instead of a wrapper dataclass.
   - **Reason**: Keeps the `items` list clean (just `Node` objects), allows input reassignment without node replacement, and avoids creating a new wrapper type that would complicate the API.
   - **Alternatives Considered**: `NodeQueueItem(node, input)` wrapper — rejected because it adds indirection and complicates node access patterns.

2. **Decision**: `advance()` calls `propagate()` on the current node before removal, guarded by a `_propagated` flag to satisfy FR-012's conditional requirement.
   - **Reason**: Ensures propagation always happens before node removal, but only once per node. The `on_complete()` hook may call `advance()` or other mutations, so propagation must happen at removal time. The guard prevents double-propagation if `propagate()` was called externally.
   - **Alternatives Considered**: (a) Unconditional `propagate()` — rejected because FR-012 requires conditional call. (b) Require `on_complete()` to call `propagate()` explicitly — rejected because it's error-prone.
   - **Mechanism**: The `_propagated` flag is opt-in: `getattr(node, "_propagated", False)` returns `False` when the attribute is absent, so nodes that don't track propagation state proceed without declaring the attribute. Do not add `_propagated` as a required field on `Node`.

3. **Decision**: `ensure_terminal()` uses `node.is_terminal` attribute for detection.
   - **Reason**: Consistent with the `Node` base class design from M1.5. The `is_terminal` flag is a data-level declaration that cannot be accidentally overridden by subclasses.
   - **Alternatives Considered**: Type-based detection (`isinstance(node, ResponseNode)`) — rejected because it couples the queue to concrete node types and prevents flexible terminal node definitions.

4. **Decision**: `spawn_after_current()` raises `ValueError` on empty queue.
   - **Reason**: Spawning after nothing is a programming error. Raising immediately catches bugs rather than silently creating invalid state.
   - **Alternatives Considered**: No-op on empty queue — rejected because it masks bugs.

5. **Decision**: Defer suspension/prepend to Milestone 1.7.
   - **Reason**: The current scope focuses on basic sequential execution and terminal safety. Suspension/prepend adds complexity that can be layered on top of the basic queue mechanics.
   - **Alternatives Considered**: Include suspension/prepend in M1.6 — rejected because it would expand scope and delay the core queue functionality.

6. **Decision**: `advance()` has return type `Node | None` — two distinct empty-queue cases:
   - **Case A** (empty BEFORE removal): `advance()` called when `items` is already empty → raises `ValueError` (FR-010).
   - **Case B** (empty AFTER removal): `advance()` called on a single-node queue, leaving zero nodes → returns `None` (FR-005).
   - **Reason**: Callers do NOT need to catch `ValueError` to distinguish "was empty" from "is now empty" — the exception only fires when the queue was already empty.

---

## Execution Flow

The `TinyCUALoop` orchestrates the execute → on_complete → advance cycle:

1. **Bootstrap**: `run()` calls `queue.ensure_terminal(default_response_node)` to guarantee a terminal response path.
2. **Read current**: Loop reads `queue.current` to get the active node.
3. **Get input**: Loop calls `queue.input_for_current()` to get the node's `NodeInputLike`.
4. **Execute node**: Loop executes the node with the retrieved input.
5. **Node completes**: The node calls `node.on_complete(queue, result)` to mutate the queue (advance, spawn, or clear).
6. **Check termination**: Loop checks if `queue.is_empty()` — if true, execution ends.
7. **Repeat**: Loop continues from step 2 with the new `queue.current`.

This cycle continues until the queue is empty or a terminal node completes. The `ensure_terminal()` bootstrap call at step 1 guarantees the queue always has a terminal node at the end, preventing infinite loops.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Propagation side effects during advance | Medium | Medium | Test with mock nodes that track propagation calls; ensure propagation happens exactly once |
| Input tracking synchronization with node removal | Low | Low | Dict cleanup in `advance()` and `clear_after_current()`; test with multiple nodes |
| Terminal detection edge cases | Low | Medium | Test with various node configurations including single-node and multi-node queues |
| Backward compatibility with M1.1 stub | Low | Low | M1.1 tests should still pass with empty queue behavior |

---

## Open Questions _(optional)_

_(None — all questions resolved. See spec.md Decisions Log (lines 122-129) for terminal detection and input tracking resolutions.)_

---

## References

- Spec: `./spec.md`
- Design docs:
  - `src/tinycua/docs/design/loops/node_queue.md` — target architecture for NodeQueue
  - `src/tinycua/docs/design/loops/tinycua_loop.md` — TinyCUALoop execution flow
  - `src/tinycua/docs/design/loops/node.md` — Node base class hierarchy
- Related milestones:
  - Milestone 1.5: Node Base, DecisionNode, ProcessNode (`specs/tinycua-node/`)
  - Milestone 1.7: Suspension/Prepend (deferred)
