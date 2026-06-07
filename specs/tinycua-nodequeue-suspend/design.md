# Design Document: NodeQueue Suspension and Prepend

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-07

---

## Overview

This design adds `suspend_current_and_prepend()` to `NodeQueue`, enabling nodes to temporarily suspend execution while keeping them queued, prepend helper nodes before them, and resume after helpers complete. This enables the ResponseNode → InformationDigesterNode handoff pattern where a response node delegates information digestion to a helper and resumes after the digest completes.

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
  · suspend_current_and_prepend(nodes) → None # preserves suspended node, inserts before
  · clear_after_current() → None         # drops queued nodes after items[0]
  · ensure_terminal(default_response_node) → None # guarantees terminal current path
  · is_empty() → bool
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/loops/node_queue.py` | Modified | Add `suspend_current_and_prepend()` method |
| `tinycua/loops/node.py` | Referenced | `Node.on_complete()` may call `suspend_current_and_prepend()` |
| `tinycua/loops/tinycua_loop.py` | Referenced | Loop orchestrates execute → on_complete cycle |

---

## Data Model

### NodeQueue (Updated)

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

    def suspend_current_and_prepend(self, nodes: list[Node]) -> None:
        """Suspend the current node and prepend new nodes before it.

        Keeps the current node queued but no longer at items[0].
        Inserts new nodes before the current node, making the first
        prepended node the new current.

        Does NOT call propagate() on the suspended node (unlike advance()).
        Raises ValueError if queue is empty. Calling with an empty list is a no-op.
        """
        if not self.items:
            raise ValueError("Cannot suspend in an empty queue")

        if not nodes:
            return

        # Insert nodes before items[0] using slice assignment
        self.items[0:0] = nodes

    def clear_after_current(self) -> None:
        """Remove all nodes after the current node.

        Removed node sessions are not mutated, and their input mappings
        are cleaned up. No further propagation occurs unless it happened
        before removal.
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

### suspend_current_and_prepend() Contract

```python
def suspend_current_and_prepend(self, nodes: list[Node]) -> None:
    """Suspend the current node and prepend new nodes before it.

    Keeps the current node queued but no longer at items[0].
    Inserts new nodes before the current node, making the first
    prepended node the new current.

    Does NOT call propagate() on the suspended node (unlike advance()).
    Raises ValueError if queue is empty. Calling with an empty list is a no-op.
    """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `suspend_current_and_prepend()` on empty queue | `ValueError("Cannot suspend in an empty queue")` | No current node to suspend |
| `suspend_current_and_prepend([])` with empty list | No-op | Consistent with `spawn_after_current([])` behavior |
| `propagate()` during suspend | Not called | Suspended node retains state until resumed |

### Input Lifecycle During Suspension

- The suspended node's `_inputs[node_id]` entry is preserved (not removed).
- Prepended nodes should have their inputs set via `set_input()` before or after calling `suspend_current_and_prepend()`.
- When `advance()` is called on a prepended node, its `_inputs[node_id]` entry is cleaned up automatically (consistent with normal `advance()` behavior).

---

## Execution Flow

### Suspension Pattern

```
Before suspension:
  [ResponseNode, ...]

ResponseNode calls suspend_current_and_prepend([InformationDigesterNode]):
  [InformationDigesterNode, ResponseNode, ...]

InformationDigesterNode executes and completes:
  → advance() removes InformationDigesterNode
  → ResponseNode becomes current (resumes)

After resume:
  [ResponseNode, ...]
```

### Queue State Transitions

1. **Initial state**: `[NodeA, NodeB]` — `NodeA` is current
2. **Suspension**: `NodeA` calls `suspend_current_and_prepend([NodeC])`
3. **After suspend**: `[NodeC, NodeA, NodeB]` — `NodeC` is current, `NodeA` is suspended
4. **NodeC completes**: `advance()` removes `NodeC`, `NodeA` becomes current
5. **Resume**: `NodeA` continues execution with preserved state

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Add `suspend_current_and_prepend()` method to `NodeQueue`
- [ ] Implement empty queue safety (raise `ValueError`)
- [ ] Implement empty list no-op behavior
- [ ] Verify no `propagate()` call during suspend
- [ ] Write comprehensive unit tests for all scenarios
- [ ] Verify backward compatibility with M1.6 tests

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- None for this milestone. Concrete node implementations (ResponseNode, InformationDigesterNode) are handled by their respective milestones.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use slice assignment `self.items[0:0] = nodes` for prepend insertion.
   - **Reason**: Consistent with `spawn_after_current()` which uses `self.items[1:1] = nodes`. Slice assignment is O(n) but maintains list integrity and is Pythonic.
   - **Alternatives Considered**: `self.items = nodes + self.items` — rejected because it creates a new list object, breaking reference identity for any external references to `items`.

2. **Decision**: Do NOT call `propagate()` on the suspended node during suspension.
   - **Reason**: The target architecture states: "suspend_current_and_prepend(nodes) → None # preserves suspended node session". Propagation should only occur when a node is removed (via `advance()`), not when it's suspended. The suspended node retains its state until it resumes and eventually completes.
   - **Alternatives Considered**: Call `propagate()` during suspend — rejected because it would prematurely commit the node's output before the helper nodes complete.

3. **Decision**: Preserve `NodeInputLike` mapping for suspended nodes.
   - **Reason**: The suspended node may need its input when it resumes. The `_inputs` dict mapping is keyed by `node_id`, so the suspended node's input remains accessible even when it's no longer at `items[0]`.
   - **Alternatives Considered**: Clear input on suspend — rejected because it would lose context needed for resume.

4. **Decision**: Raise `ValueError` on empty queue, no-op on empty list.
   - **Reason**: Consistent with `spawn_after_current()` behavior. Empty queue is a programming error (no node to suspend). Empty list is a valid no-op (suspend without prepending anything).
   - **Alternatives Considered**: No-op on empty queue — rejected because it masks bugs.

5. **Decision**: Defer concrete node implementations to their respective milestones.
   - **Reason**: This milestone focuses on the queue mechanism. Concrete nodes (ResponseNode, InformationDigesterNode) will use this mechanism in later milestones.
   - **Alternatives Considered**: Include concrete nodes — rejected because it would expand scope and delay the core queue functionality.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Nested suspension complexity | Medium | Medium | Test with multiple sequential suspensions; ensure queue state is always consistent |
| Input mapping desynchronization | Low | Low | Dict cleanup in `advance()` and `clear_after_current()`; test with suspended nodes |
| Backward compatibility with M1.6 | Low | High | Run existing M1.6 test suite; `suspend_current_and_prepend()` is additive and does not modify existing methods |
| Performance with large queues | Low | Low | Slice assignment is O(n) but acceptable for typical queue sizes (< 100 nodes) |

---

## Open Questions _(optional)_

1. **Should `suspend_current_and_prepend()` accept a single node or only a list?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-07
   - **Status**: Proposed
   - **Proposed Answer**: Accept `list[Node]` for consistency with `spawn_after_current()`. Callers can pass `[node]` for single-node suspension.

2. **How should the loop detect that a node was suspended vs. completed?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-07
   - **Status**: Resolved
   - **Resolution**: The loop does not need to distinguish — it simply reads `queue.current` after `on_complete()` returns. If the node was suspended, `queue.current` will be the first prepended node. If the node completed normally (via `advance()`), `queue.current` will be the next node or `None`.

---

## References

- Spec: `./spec.md`
- Design docs:
  - `src/tinycua/docs/design/loops/node_queue.md` — target architecture for NodeQueue
  - `src/tinycua/docs/design/loops/tinycua_loop.md` — TinyCUALoop execution flow
  - `src/tinycua/docs/design/loops/node.md` — Node base class hierarchy
- Related milestones:
  - Milestone 1.5: Node Base, DecisionNode, ProcessNode (`specs/tinycua-node/`)
  - Milestone 1.6: NodeQueue Basic Execution and Terminal Safety (`specs/tinycua-nodequeue-basic/`)

---

## Review Checklist

- [x] All mandatory sections completed (Overview, Architecture, Data Model, API Contracts, Execution Flow, Technical Decisions, Risks)
- [x] API contracts consistent with spec requirements (FR-001 through FR-008)
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Technical decisions include rationale and alternatives considered
- [x] Error handling table covers all spec edge cases
- [x] Risks and mitigations are complete
