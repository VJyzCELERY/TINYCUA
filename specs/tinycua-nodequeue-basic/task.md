# Tasks: NodeQueue Basic Execution and Terminal Safety

Implementation tasks for NodeQueue Basic Execution and Terminal Safety. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write comprehensive unit tests for NodeQueue (see implementation-plan.md Success Criteria) <!-- id: 0 -->
  - [ ] Test `current` property (returns first node, returns None when empty)
  - [ ] Test `is_empty()` (returns True when empty, False when not)
  - [ ] Test `advance()` (removes current, calls propagate, returns new current, raises on empty)
  - [ ] Test `spawn_after_current()` (inserts after current, does not change current, raises on empty)
  - [ ] Test `clear_after_current()` (removes after current, no-op when single/empty)
  - [ ] Test `ensure_terminal()` (appends when missing, no-op when exists, works on empty)
  - [ ] Test input tracking (`input_for_current()`, `set_input()`, cleanup on removal)
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Replace M1.1 NodeQueue stub with full implementation <!-- id: 2 -->
  - [ ] Change `items` type from `list[Any]` to `list[Node]`
  - [ ] Add `_inputs: dict[str, NodeInputLike]` internal mapping
  - [ ] Convert `current` from attribute to property returning `items[0]` or `None`
  - [ ] Implement `is_empty()` checking `len(self.items) == 0`
  - [ ] Implement `input_for_current()` returning stored input or empty dict
  - [ ] Implement `set_input(node, input_data)` for input tracking
- [ ] Implement `advance()` method <!-- id: 3 -->
  - [ ] Raise `ValueError("Cannot advance an empty queue")` when empty
  - [ ] Call `propagate()` on current node before removal
  - [ ] Remove `items[0]` and clean up `_inputs` entry
  - [ ] Return new current node or `None`
- [ ] Implement `spawn_after_current()` method <!-- id: 4 -->
  - [ ] Raise `ValueError("Cannot spawn after an empty queue")` when empty
  - [ ] Insert nodes after `items[0]` using slice assignment `self.items[1:1] = nodes`
  - [ ] Verify current remains unchanged
- [ ] Implement `clear_after_current()` method <!-- id: 5 -->
  - [ ] No-op when queue is empty or has only one node
  - [ ] Remove all nodes after `items[0]` and clean up their `_inputs` entries
- [ ] Implement `ensure_terminal()` method <!-- id: 6 -->
  - [ ] Append default terminal node when queue is empty
  - [ ] Append default terminal when last node has `is_terminal=False`
  - [ ] No-op when last node has `is_terminal=True`
- [ ] Update `__init__.py` exports <!-- id: 7 -->
  - [ ] Add `NodeQueue` to `__all__` in `tinycua/loops/__init__.py`

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 8 -->
- [ ] Write unit tests for TinyCUALoop `ensure_terminal()` bootstrap <!-- id: 9 -->
  - [ ] Test that `run()` calls `ensure_terminal()` on queue
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 10 -->

## Verification Phase

- [ ] Verify existing M1.1 tests updated and passing <!-- id: 11 -->
- [ ] Verify `NodeQueue` works with mock nodes in isolation <!-- id: 12 -->
- [ ] Verify `advance()` propagates exactly once per node <!-- id: 13 -->

## Documentation Phase

- [ ] Update module docstring in `node_queue.py` to describe full functionality <!-- id: 14 -->
- [ ] Update design.md implementation checklist to mark completed items <!-- id: 15 -->

## Review and Merge

- [ ] Create pull request <!-- id: 16 -->
- [ ] Address review feedback <!-- id: 17 -->
- [ ] Merge to main branch <!-- id: 18 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-07*
