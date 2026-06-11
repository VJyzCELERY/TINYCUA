# Tasks: Mandatory Passthrough and Continuation Routing

Implementation tasks for Mandatory Passthrough and Continuation Routing (Milestone 3.3). Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write unit tests for `_on_reviewer_open_question` installing MandatoryPassthrough <!-- id: 0 -->
- [ ] Write unit tests for `_install_mandatory_passthrough`, `_clear_mandatory_passthrough`, `_find_result_reviewer` <!-- id: 1 -->
- [ ] Write unit tests for `_execute_decision_node` passthrough injection and consumption <!-- id: 2 -->
- [ ] Write integration test for end-to-end open_question → passthrough → continuation <!-- id: 3 -->
- [ ] Run all new tests — expect RED (failures) since no implementation yet <!-- id: 4 -->

## Implementation Phase

- [ ] Add `_pending_mandatory_passthrough: MandatoryPassthrough | None = None` field to `TinyCUALoop.__init__` <!-- id: 5 -->
- [ ] Implement `_install_mandatory_passthrough(self, mandatory)` method on `TinyCUALoop` <!-- id: 6 -->
- [ ] Implement `_clear_mandatory_passthrough(self)` method on `TinyCUALoop` <!-- id: 7 -->
- [ ] Implement `_find_result_reviewer(self)` method on `TinyCUALoop` — scan queue for `TinyCUAResultReviewerNode` <!-- id: 8 -->
- [ ] Update `_on_reviewer_open_question(self, active_task)` from log-only stub to install MandatoryPassthrough <!-- id: 9 -->
- [ ] Update `_execute_decision_node()` to inject `_pending_mandatory_passthrough` into QueryAnalyst input metadata before precheck <!-- id: 10 -->
- [ ] Update `_execute_decision_node()` to call `_clear_mandatory_passthrough()` after successful passthrough forward <!-- id: 11 -->

## Testing Phase

- [ ] Run all new tests — expect GREEN (all pass) <!-- id: 12 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` — confirm no regressions <!-- id: 13 -->

## Verification Phase

- [ ] Verify `_on_reviewer_open_question` installs passthrough with correct `target_node_id` and `target_session_id` <!-- id: 14 -->
- [ ] Verify stale passthrough (session mismatch) falls back to LLM classification <!-- id: 15 -->
- [ ] Verify active task is preserved (not mutated) during passthrough cycle <!-- id: 16 -->
- [ ] Verify passthrough is cleared after successful forward — no stale re-use <!-- id: 17 -->

## Documentation Phase

- [ ] Update spec.md Status Tracker — mark completed items <!-- id: 18 -->

## Review and Merge

- [ ] Create pull request <!-- id: 19 -->
- [ ] Address review feedback <!-- id: 20 -->
- [ ] Merge to main branch <!-- id: 21 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-11*
