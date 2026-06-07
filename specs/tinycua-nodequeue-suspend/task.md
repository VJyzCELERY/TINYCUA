# Tasks: NodeQueue Suspension and Prepend

Implementation tasks for NodeQueue Suspension and Prepend. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write unit tests in `src/tinycua/tests/unit/test_node_queue_suspend.py` (all scenarios from implementation-plan.md) <!-- id: 0 -->
- [ ] Run unit tests — expect RED (failures since `suspend_current_and_prepend` does not exist yet) <!-- id: 1 -->

## Implementation Phase

- [ ] Add `suspend_current_and_prepend(self, nodes: list[Node]) -> None` method to `NodeQueue` in `src/tinycua/tinycua/loops/node_queue.py` <!-- id: 2 -->
  - [ ] Raise `ValueError("Cannot suspend in an empty queue")` when queue is empty
  - [ ] Return early (no-op) when `nodes` list is empty
  - [ ] Use slice assignment `self.items[0:0] = nodes` to prepend nodes before current
  - [ ] Do NOT call `propagate()` on the suspended node
  - [ ] Preserve `_inputs` mapping for the suspended node (no cleanup needed — dict is keyed by node_id)

## Testing Phase

- [ ] Run unit tests — expect GREEN (all pass) <!-- id: 3 -->
- [ ] Write unit tests for edge cases: nested suspensions, clear_after_current with suspended nodes <!-- id: 4 -->
- [ ] Write test for nested suspension scenario (spec scenario 9) <!-- id: 4a -->
- [ ] Write test for clear_after_current with suspended node <!-- id: 4b -->
- [ ] Write test for prepended node input lifecycle (implementation-plan.md Scenario 10) <!-- id: 4c -->
- [ ] Write test for output propagation / input preservation after advance (implementation-plan.md Scenario 11) <!-- id: 4d -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 5 -->

## Verification Phase

- [ ] Verify `queue.current` returns prepended node after suspension <!-- id: 6 -->
- [ ] Verify `advance()` on prepended node returns suspended node as new current <!-- id: 7 -->
- [ ] Verify suspended node's input mapping is preserved via `_inputs` dict <!-- id: 8 -->
- [ ] Verify backward compatibility — existing M1.6 tests pass without modification <!-- id: 9 -->
- [ ] Run lint: `cd src/tinycua && uv run ruff check .` <!-- id: 14 -->
- [ ] Run type check: `cd src/tinycua && uv run mypy tinycua/` <!-- id: 15 -->

## Documentation Phase

- [ ] Update spec.md status tracker — mark completed items <!-- id: 10 -->

## Review and Merge

- [ ] Create pull request <!-- id: 11 -->
- [ ] Address review feedback <!-- id: 12 -->
- [ ] Merge to main branch <!-- id: 13 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-07*
