# Implementation: NodeQueue Basic Execution and Terminal Safety

Replace the M1.1 `NodeQueue` stub with a functional sequential execution structure supporting `advance()`, `spawn_after_current()`, `clear_after_current()`, and `ensure_terminal()`. This enables `TinyCUALoop` to execute nodes through the queue with terminal safety guarantees.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| - [x] **None** — no external services needed | | | |

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.12+, uv
- [x] **Package manager**: uv

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/unit/test_node_queue.py
"""Integration tests for NodeQueue basic execution and terminal safety."""

import pytest
from unittest.mock import MagicMock
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.node import Node


def _make_node(node_id: str, *, is_terminal: bool = False) -> MagicMock:
    """Create a mock node with required attributes."""
    node = MagicMock(spec=Node)
    node.node_id = node_id
    node.is_terminal = is_terminal
    node.propagate = MagicMock()
    return node


class TestNodeQueueCurrent:
    """Tests for current property."""

    def test_current_returns_first_node(self):
        """queue.current returns items[0] when present."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]
        assert queue.current is node_a

    def test_current_returns_none_when_empty(self):
        """queue.current returns None when queue is empty."""
        queue = NodeQueue()
        assert queue.current is None


class TestNodeQueueIsEmpty:
    """Tests for is_empty()."""

    def test_is_empty_returns_true_when_empty(self):
        """is_empty() returns True when items is empty."""
        queue = NodeQueue()
        assert queue.is_empty() is True

    def test_is_empty_returns_false_when_not_empty(self):
        """is_empty() returns False when items has nodes."""
        queue = NodeQueue()
        queue.items = [_make_node("a")]
        assert queue.is_empty() is False


class TestNodeQueueAdvance:
    """Tests for advance()."""

    def test_advance_removes_current_node(self):
        """advance() removes items[0] after calling propagate()."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        queue.items = [node_a, node_b]

        result = queue.advance()

        node_a.propagate.assert_called_once()
        assert result is node_b
        assert queue.items == [node_b]

    def test_advance_returns_none_when_queue_becomes_empty(self):
        """advance() returns None when queue becomes empty after removal."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        result = queue.advance()

        assert result is None
        assert queue.is_empty()

    def test_advance_raises_on_empty_queue(self):
        """advance() raises ValueError on empty queue."""
        queue = NodeQueue()
        with pytest.raises(ValueError, match="Cannot advance an empty queue"):
            queue.advance()

    def test_advance_calls_propagate_before_removal(self):
        """advance() calls propagate() before removing the node."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        queue.advance()

        node_a.propagate.assert_called_once()

    def test_advance_skips_propagation_if_already_propagated(self):
        """advance() skips propagate() if node has _propagated flag set."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_a._propagated = True
        queue.items = [node_a]

        queue.advance()

        node_a.propagate.assert_not_called()


class TestNodeQueueSpawn:
    """Tests for spawn_after_current()."""

    def test_spawn_inserts_after_current(self):
        """spawn_after_current() inserts nodes after items[0]."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        node_c = _make_node("c")
        queue.items = [node_a, node_b]

        queue.spawn_after_current([node_c])

        assert queue.items == [node_a, node_c, node_b]
        assert queue.current is node_a

    def test_spawn_does_not_change_current(self):
        """spawn_after_current() does not change current node."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        queue.items = [node_a]

        queue.spawn_after_current([node_b])

        assert queue.current is node_a

    def test_spawn_raises_on_empty_queue(self):
        """spawn_after_current() raises ValueError on empty queue."""
        queue = NodeQueue()
        with pytest.raises(ValueError, match="Cannot spawn after an empty queue"):
            queue.spawn_after_current([_make_node("x")])

    def test_spawn_with_empty_list_is_noop(self):
        """spawn_after_current([]) is a no-op."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        queue.spawn_after_current([])

        assert queue.items == [node_a]


class TestNodeQueueClear:
    """Tests for clear_after_current()."""

    def test_clear_removes_nodes_after_current(self):
        """clear_after_current() removes all nodes after items[0]."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        node_c = _make_node("c")
        queue.items = [node_a, node_b, node_c]

        queue.clear_after_current()

        assert queue.items == [node_a]

    def test_clear_is_noop_when_only_current(self):
        """clear_after_current() is a no-op when only one node exists."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        queue.clear_after_current()

        assert queue.items == [node_a]

    def test_clear_is_noop_when_empty(self):
        """clear_after_current() is a no-op when queue is empty."""
        queue = NodeQueue()
        queue.clear_after_current()
        assert queue.is_empty()


class TestNodeQueueEnsureTerminal:
    """Tests for ensure_terminal()."""

    def test_ensure_terminal_appends_when_no_terminal(self):
        """ensure_terminal() appends default when last node is not terminal."""
        queue = NodeQueue()
        node_a = _make_node("a", is_terminal=False)
        node_b = _make_node("b", is_terminal=False)
        queue.items = [node_a, node_b]
        terminal = _make_node("response", is_terminal=True)

        queue.ensure_terminal(terminal)

        assert queue.items == [node_a, node_b, terminal]

    def test_ensure_terminal_noop_when_terminal_exists(self):
        """ensure_terminal() is a no-op when last node is terminal."""
        queue = NodeQueue()
        node_a = _make_node("a", is_terminal=False)
        terminal = _make_node("response", is_terminal=True)
        queue.items = [node_a, terminal]
        default = _make_node("default_response", is_terminal=True)

        queue.ensure_terminal(default)

        assert queue.items == [node_a, terminal]

    def test_ensure_terminal_appends_to_empty_queue(self):
        """ensure_terminal() appends to empty queue."""
        queue = NodeQueue()
        terminal = _make_node("response", is_terminal=True)

        queue.ensure_terminal(terminal)

        assert queue.items == [terminal]


class TestNodeQueueInputTracking:
    """Tests for input_for_current() and set_input()."""

    def test_input_for_current_returns_stored_input(self):
        """input_for_current() returns stored input for current node."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]
        queue.set_input(node_a, {"query": "test"})

        assert queue.input_for_current() == {"query": "test"}

    def test_input_for_current_returns_empty_when_no_input(self):
        """input_for_current() returns empty dict when no input is set."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        assert queue.input_for_current() == {}

    def test_input_for_current_returns_empty_when_empty_queue(self):
        """input_for_current() returns empty dict when queue is empty."""
        queue = NodeQueue()
        assert queue.input_for_current() == {}
```

> **Note**: These scenarios are defined as testable milestones. Checkboxes track completion status.

### Key Test Scenarios

- [x] **Scenario 1**: Queue current returns `items[0]` when present, `None` when empty — primary access pattern
- [x] **Scenario 2**: `advance()` propagates then removes current, returns next node — core execution flow
- [x] **Scenario 3**: `spawn_after_current()` inserts without changing current — dynamic queue mutation
- [x] **Scenario 4**: `ensure_terminal()` appends terminal node when missing — safety invariant
- [x] **Edge case**: `advance()` on empty queue raises `ValueError` — error safety
- [x] **Edge case**: Input tracking stays synchronized with node removal

## Verification Plan

> **Note**: Tests are defined above and ready to execute. Checkboxes below track execution status, not authoring status.

### Automated Tests

- [x] Integration tests (defined above) — these must pass for implementation to be complete
- [x] Unit tests for NodeQueue — test error handling, edge cases, fallbacks
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [x] Verify existing M1.1 tests still pass (empty queue behavior preserved)
- [x] Verify `NodeQueue` can be instantiated and used with mock nodes

### Performance Considerations

- [x] No performance concerns for this milestone — O(1) operations on list head

## Proposed Changes

### NodeQueue Module

#### [MODIFY] `src/tinycua/tinycua/loops/node_queue.py`

- **Description of change**: Replace M1.1 stub with full implementation including `current` property, `is_empty()`, `input_for_current()`, `set_input()`, `advance()`, `spawn_after_current()`, `clear_after_current()`, and `ensure_terminal()`.
- **Rationale**: This is the core implementation for Milestone 1.6. The stub must be replaced with functional sequential queue semantics.
- **Breaking changes**: Yes — `advance()` now raises `ValueError` on empty queue instead of being a no-op. `current` changes from an attribute to a property. Input tracking via `_inputs` dict is new.

#### [MODIFY] `src/tinycua/tinycua/loops/__init__.py`

- **Description of change**: Add `NodeQueue` to the `__all__` exports.
- **Rationale**: `NodeQueue` is now a first-class component and should be importable from the loops package.

### TinyCUALoop Integration

#### [MODIFY] `src/tinycua/tinycua/loops/tinycua_loop.py`

- **Description of change**: Add `ensure_terminal()` call at queue bootstrap in `run()` method.
- **Rationale**: Terminal safety invariant must be enforced at loop start.
- **Note**: Full node execution integration is deferred to the implementation phase — this step only adds the bootstrap safety call.

### Test Updates

#### [MODIFY] `src/tinycua/tests/unit/test_node_queue.py`

- **Description of change**: Replace M1.1 stub tests with comprehensive tests for all NodeQueue methods.
- **Rationale**: Tests define the contract and must be written first (TDD).

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `NodeQueue` | Modify | Replace M1.1 stub with full sequential execution queue |
| `TinyCUALoop` | Modify (minor) | Add `ensure_terminal()` bootstrap call |
| `Node` | Referenced | No changes — uses existing `is_terminal`, `propagate()`, `on_complete()` |

## Data Model Changes

```python
# NodeQueue (replaces M1.1 stub)
@dataclass
class NodeQueue:
    items: list[Node]          # Backing store — items[0] is active node
    _inputs: dict[str, NodeInputLike]  # node_id → input mapping

    @property
    def current(self) -> Node | None:
        """Return items[0] or None."""

    def is_empty(self) -> bool: ...
    def input_for_current(self) -> NodeInputLike: ...
    def set_input(self, node: Node, input_data: NodeInputLike) -> None: ...
    def advance(self) -> Node | None: ...
    def spawn_after_current(self, nodes: list[Node]) -> None: ...
    def clear_after_current(self) -> None: ...
    def ensure_terminal(self, default_terminal_node: Node) -> None: ...
```

## API Changes

### New Methods

| Method | Description |
|--------|-------------|
| `NodeQueue.spawn_after_current(nodes)` | Insert nodes after current without changing current |
| `NodeQueue.clear_after_current()` | Remove all nodes after current |
| `NodeQueue.ensure_terminal(default)` | Append terminal node if none exists |
| `NodeQueue.set_input(node, input_data)` | Set input data for a specific node |

### Modified Methods

| Method | Change |
|--------|--------|
| `NodeQueue.advance()` | Now raises `ValueError` on empty queue, calls `propagate()` before removal, returns new current |
| `NodeQueue.current` | Changed from attribute to property returning `items[0]` or `None` |
| `NodeQueue.is_empty()` | Now checks `len(self.items) == 0` instead of always returning `True` |
| `NodeQueue.input_for_current()` | Now returns stored input from `_inputs` dict instead of empty dict |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none) | — | No new external dependencies |

### Internal Dependencies

- [x] Depends on `Node` base class (M1.5) — already exists
- [x] Depends on `NodeInputLike` type (M1.5) — already exists
- [x] Blocks: Full `TinyCUALoop` node execution integration (future milestone)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking change in `advance()` (no-op → raises ValueError) | Medium | Update all callers; existing M1.1 tests only test empty queue, so they must be updated |
| Propagation side effects during advance | Medium | Test with mock nodes that track propagation calls; ensure propagation happens exactly once |
| Input tracking synchronization with node removal | Low | Dict cleanup in `advance()` and `clear_after_current()`; test with multiple nodes |
| Terminal detection edge cases | Low | Test with various node configurations including single-node and multi-node queues |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-07*
