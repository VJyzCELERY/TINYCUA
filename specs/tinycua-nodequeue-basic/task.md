# Tasks: NodeQueue Basic Execution and Terminal Safety

Implementation tasks for NodeQueue Basic Execution and Terminal Safety. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write comprehensive unit tests for NodeQueue (see implementation-plan.md Success Criteria) <!-- id: 0 -->
  - [x] Test `current` property (returns first node, returns None when empty)
  - [x] Test `is_empty()` (returns True when empty, False when not)
  - [x] Test `advance()` (removes current, calls propagate, returns new current, raises on empty)
  - [x] Test `spawn_after_current()` (inserts after current, does not change current, raises on empty)
  - [x] Test `clear_after_current()` (removes after current, no-op when single/empty)
  - [x] Test `ensure_terminal()` (appends when missing, no-op when exists, works on empty)
  - [x] Test input tracking (`input_for_current()`, `set_input()`, cleanup on removal)
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [x] Replace M1.1 NodeQueue stub with full implementation <!-- id: 2 -->
  - [x] Change `items` type from `list[Any]` to `list[Node]`
  - [x] Add `_inputs: dict[str, NodeInputLike]` internal mapping
  - [x] Convert `current` from attribute to property returning `items[0]` or `None`
  - [x] Implement `is_empty()` checking `len(self.items) == 0`
  - [x] Implement `input_for_current()` returning stored input or empty dict
- [x] Implement `set_input(node, input_data)` for input tracking <!-- id: 3 -->
- [x] Implement `advance()` method <!-- id: 4 -->
  - [x] Raise `ValueError("Cannot advance an empty queue")` when empty
  - [x] Call `propagate()` on current node before removal
  - [x] Remove `items[0]` and clean up `_inputs` entry
  - [x] Return new current node or `None`
- [x] Implement `spawn_after_current()` method <!-- id: 5 -->
  - [x] Raise `ValueError("Cannot spawn after an empty queue")` when empty
  - [x] Insert nodes after `items[0]` using slice assignment `self.items[1:1] = nodes`
  - [x] Verify current remains unchanged
- [x] Implement `clear_after_current()` method <!-- id: 6 -->
  - [x] No-op when queue is empty or has only one node
  - [x] Remove all nodes after `items[0]` and clean up their `_inputs` entries
- [x] Implement `ensure_terminal()` method <!-- id: 7 -->
  - [x] Append default terminal node when queue is empty
  - [x] Append default terminal when last node has `is_terminal=False`
  - [x] No-op when last node has `is_terminal=True`
- [x] Update `__init__.py` exports <!-- id: 8 -->
  - [x] Add `NodeQueue` to `__all__` in `tinycua/loops/__init__.py`

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 9 -->
- [x] Write unit tests for TinyCUALoop `ensure_terminal()` bootstrap <!-- id: 10 -->
  - [x] Test that `run()` calls `ensure_terminal()` on queue
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 11 -->

## Verification Phase

- [x] Verify existing M1.1 tests updated and passing <!-- id: 12 -->
- [x] Verify `NodeQueue` works with mock nodes in isolation <!-- id: 13 -->
- [x] Verify `advance()` propagates exactly once per node <!-- id: 14 -->

## Documentation Phase

- [x] Update module docstring in `node_queue.py` to describe full functionality <!-- id: 15 -->
- [x] Update design.md implementation checklist to mark completed items <!-- id: 16 -->

## Review and Merge

- [ ] Create pull request <!-- id: 17 -->
- [ ] Address review feedback <!-- id: 18 -->
- [ ] Merge to main branch <!-- id: 19 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-07*
