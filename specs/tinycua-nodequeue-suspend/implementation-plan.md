# Implementation: NodeQueue Suspension and Prepend

Add `suspend_current_and_prepend()` to `NodeQueue`, enabling nodes to temporarily suspend execution while keeping them queued, prepend helper nodes before them, and resume after helpers complete. This enables the ResponseNode → InformationDigesterNode handoff pattern.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: S

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| - [x] **None** — no external services needed |

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Unit Tests (TDD First)

Define the unit tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/unit/test_node_queue_suspend.py
"""Unit tests for NodeQueue suspension and prepend."""

# Helper: _make_node() — copy of helper from test_node_queue.py
def _make_node(node_id: str, *, is_terminal: bool = False) -> MagicMock:
    node = MagicMock(spec=Node)
    node.node_id = node_id
    node.is_terminal = is_terminal
    node.propagate = MagicMock()
    return node


def test_suspend_keeps_current_queued_and_prepends_before_it():
    """suspend_current_and_prepend() keeps current node queued,
    inserts new nodes before it, and makes first prepended node current."""
    queue = NodeQueue()
    node_a = _make_node("a")
    node_b = _make_node("b")
    node_c = _make_node("c")
    queue.items = [node_a, node_b]

    queue.suspend_current_and_prepend([node_c])

    assert queue.items == [node_c, node_a, node_b]
    assert queue.current is node_c


def test_suspend_with_single_node():
    """suspend_current_and_prepend([NodeB]) on [NodeA] yields [NodeB, NodeA]."""
    queue = NodeQueue()
    node_a = _make_node("a")
    node_b = _make_node("b")
    queue.items = [node_a]

    queue.suspend_current_and_prepend([node_b])

    assert queue.items == [node_b, node_a]
    assert queue.current is node_b


def test_suspend_with_multiple_nodes():
    """suspend_current_and_prepend([NodeC, NodeD]) on [NodeA, NodeB]
    yields [NodeC, NodeD, NodeA, NodeB]."""
    queue = NodeQueue()
    node_a = _make_node("a")
    node_b = _make_node("b")
    node_c = _make_node("c")
    node_d = _make_node("d")
    queue.items = [node_a, node_b]

    queue.suspend_current_and_prepend([node_c, node_d])

    assert queue.items == [node_c, node_d, node_a, node_b]
    assert queue.current is node_c


def test_suspend_empty_list_is_noop():
    """suspend_current_and_prepend([]) is a no-op."""
    queue = NodeQueue()
    node_a = _make_node("a")
    queue.items = [node_a]

    queue.suspend_current_and_prepend([])

    assert queue.items == [node_a]
    assert queue.current is node_a


def test_suspend_empty_queue_raises_value_error():
    """suspend_current_and_prepend() on empty queue raises ValueError."""
    queue = NodeQueue()
    with pytest.raises(ValueError, match="Cannot suspend in an empty queue"):
        queue.suspend_current_and_prepend([_make_node("x")])


def test_suspend_does_not_call_propagate():
    """suspend_current_and_prepend() does NOT call propagate() on suspended node."""
    queue = NodeQueue()
    node_a = _make_node("a")
    queue.items = [node_a]

    queue.suspend_current_and_prepend([_make_node("b")])

    node_a.propagate.assert_not_called()


def test_suspend_preserves_input_mapping():
    """Suspended node's input mapping is preserved after suspension."""
    queue = NodeQueue()
    node_a = _make_node("a")
    node_b = _make_node("b")
    queue.items = [node_a]
    queue.set_input(node_a, {"query": "test"})

    queue.suspend_current_and_prepend([node_b])

    # Suspended node's input should still be accessible after suspension
    assert queue._inputs.get("a") == {"query": "test"}


def test_suspend_prepended_node_input_lifecycle():
    """Prepended node can have input assigned and is cleaned up on advance."""
    queue = NodeQueue()
    node_a = _make_node("a")
    node_b = _make_node("b")
    queue.items = [node_a]

    queue.suspend_current_and_prepend([node_b])
    queue.set_input(node_b, {"prepended": "input"})

    # Prepended node should have its input accessible
    assert queue.input_for_current() == {"prepended": "input"}

    # After advance, prepended node input is cleaned up
    queue.advance()
    assert queue._inputs.get("b") is None or queue._inputs.get("b") == {}

    # Suspended node resumes with its input preserved
    assert queue.current is node_a
    assert queue._inputs.get("a") is not None


def test_suspend_output_propagation_to_parent():
    """Prepended child's output reaches suspended parent upon child completion."""
    queue = NodeQueue()
    node_a = _make_node("a")
    node_b = _make_node("b")
    queue.items = [node_a]
    queue.set_input(node_a, {"query": "original"})

    # Suspend node_a, prepend node_b
    queue.suspend_current_and_prepend([node_b])
    queue.set_input(node_b, {"task": "digest"})

    # node_b completes — advance() removes it, node_a resumes
    queue.advance()

    # node_a is now current with its preserved input
    assert queue.current is node_a
    assert queue._inputs.get("a") == {"query": "original"}
    # node_b's input is cleaned up
    assert queue._inputs.get("b") is None or queue._inputs.get("b") == {}


def test_suspend_resume_after_advance():
    """Suspended node resumes when prepended node completes and advance() is called."""
    queue = NodeQueue()
    node_a = _make_node("a")
    node_b = _make_node("b")
    queue.items = [node_a]

    queue.suspend_current_and_prepend([node_b])
    assert queue.current is node_b

    # Simulate node_b completing
    queue.advance()

    assert queue.current is node_a


def test_suspend_nested_suspension_queue_state():
    """Nested suspensions: NodeA suspends for [NodeB], then NodeB suspends for [NodeC].
    Queue becomes [NodeC, NodeB, NodeA] with NodeC as current."""
    queue = NodeQueue()
    node_a = _make_node("a")
    node_b = _make_node("b")
    node_c = _make_node("c")
    queue.items = [node_a]

    # First suspension: NodeA suspends for NodeB
    queue.suspend_current_and_prepend([node_b])
    assert queue.items == [node_b, node_a]
    assert queue.current is node_b

    # Second suspension: NodeB suspends for NodeC
    queue.suspend_current_and_prepend([node_c])
    assert queue.items == [node_c, node_b, node_a]
    assert queue.current is node_c


def test_clear_after_current_with_suspended_node():
    """clear_after_current() removes nodes after current. If suspended node
    is at items[1] (after current), it IS cleared. Suspended node is only
    'preserved' if it is not in the clear zone."""
    queue = NodeQueue()
    node_a = _make_node("a")   # will be suspended
    node_b = _make_node("b")   # tail node
    node_d = _make_node("d")   # prepended node (distinct from queue nodes)
    queue.items = [node_a, node_b]
    # Suspend node_a (current), prepend node_d — queue: [node_d, node_a, node_b]
    # node_a is now suspended at items[1] (in the clear zone)
    queue.suspend_current_and_prepend([node_d])
    # clear_after_current removes items[1:] = [node_a, node_b], including suspended node_a
    queue.clear_after_current()
    # Result: only node_d remains — suspended node_a IS cleared
    assert queue.items == [node_d]
```

### Key Test Scenarios

- [ ] **Scenario 1**: Basic suspension — current node stays queued, new nodes inserted before it, first prepended node becomes current
- [ ] **Scenario 2**: Multiple prepended nodes — relative order preserved
- [ ] **Scenario 3**: Empty list no-op — no change to queue
- [ ] **Scenario 4**: Empty queue ValueError — programming error safety
- [ ] **Scenario 5**: No propagation during suspend — suspended node retains state
- [ ] **Scenario 6**: Input preservation — suspended node's input mapping survives
- [ ] **Scenario 7**: Resume after advance — suspended node becomes current after helpers complete
- [ ] **Scenario 8**: Nested suspension — second suspension prepends before first suspended node
- [ ] **Scenario 9**: clear_after_current with suspended node — suspended node IS cleared if in clear zone
- [ ] **Scenario 10**: Prepended node input lifecycle — input assignable, accessible, cleaned up on advance
- [ ] **Scenario 11**: Output propagation — prepended child's output reaches suspended parent upon completion

## Verification Plan

### Automated Tests

- [ ] Unit tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for suspension edge cases (nested suspends, clear_after_current with suspended nodes) <!-- NOTE: all tests in this doc are unit-level -->
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`
- [ ] Lint passes: `cd src/tinycua && uv run ruff check .`
- [ ] Type check passes: `cd src/tinycua && uv run mypy tinycua/`

### Manual Verification

- [ ] Verify `queue.current` returns prepended node, not suspended node
- [ ] Verify `advance()` on prepended node returns suspended node as new current

### Performance Considerations

- [ ] Slice assignment is O(n) but acceptable for typical queue sizes (< 100 nodes)

## Proposed Changes

### NodeQueue Module

#### [MODIFY] src/tinycua/tinycua/loops/node_queue.py

- **Add `suspend_current_and_prepend()` method**: Insert nodes before items[0] using slice assignment `self.items[0:0] = nodes`. Raise `ValueError` on empty queue. No-op on empty list. Do NOT call `propagate()` on the suspended node.
- **Rationale**: Core feature requirement from spec FR-001 through FR-008.

#### [MODIFY] src/tinycua/tests/unit/test_node_queue.py (or new file)

- **Add comprehensive tests**: All scenarios defined in success criteria above.
- **Rationale**: TDD approach — tests written first, implementation follows.

### No Other File Changes Required

The design doc references `node.py` and `tinycua_loop.py` as "Referenced" but not modified — the `suspend_current_and_prepend()` method is called BY those components, not defined in them.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/loops/node_queue.py` | Modify | Add `suspend_current_and_prepend()` method |

## Data Model Changes

No new types. The existing `NodeQueue` dataclass gains one new method. The `_inputs` dict mapping is already in place and will naturally preserve suspended node inputs.

## API Changes

### New Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `suspend_current_and_prepend` | `(nodes: list[Node]) -> None` | Suspend current node, prepend new nodes before it |

### Error Handling

| Error Case | Exception | Notes |
|------------|-----------|-------|
| Empty queue | `ValueError("Cannot suspend in an empty queue")` | No current node to suspend |
| Empty list | No-op | Consistent with `spawn_after_current([])` |

## Dependencies

### External Dependencies

None — this is a pure internal method addition.

### Internal Dependencies

- [x] Depends on existing `NodeQueue` infrastructure (items, _inputs, advance())
- [x] Does not block any other feature — additive change only

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Nested suspension complexity | Medium | Test with multiple sequential suspensions; ensure queue state is always consistent |
| Input mapping desynchronization | Low | Dict cleanup in `advance()` and `clear_after_current()` already handles this |
| Backward compatibility with M1.6 | Low | Run existing M1.6 test suite; method is additive and does not modify existing methods |
| Performance with large queues | Low | Slice assignment is O(n) but acceptable for typical queue sizes |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-07*
