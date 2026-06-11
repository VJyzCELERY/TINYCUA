# Tasks: Mandatory Passthrough and Continuation Routing

**Last Updated**: 2026-06-11 (review-revision-2)

Implementation tasks for Mandatory Passthrough and Continuation Routing (Milestone 3.3). Check off items as completed.

## TDD Phase (Tests First)

- [x] Write unit tests for `_on_reviewer_open_question` installing MandatoryPassthrough <!-- id: 0 -->
- [x] Write unit tests for `_install_mandatory_passthrough`, `_clear_mandatory_passthrough`, `_find_result_reviewer` <!-- id: 1 -->
- [x] Write unit tests for `_execute_decision_node` passthrough injection and consumption <!-- id: 2 -->
- [x] Write unit tests for `_ensure_query_analyst_at_front` queue restart logic <!-- id: 2b -->
- [x] Write integration test for two-call end-to-end open_question → passthrough → continuation <!-- id: 3 -->
- [x] Run all new tests — expect RED (failures) since no implementation yet <!-- id: 4 -->

## Implementation Phase

- [x] Add `_pending_mandatory_passthrough: MandatoryPassthrough | None = None` field to `TinyCUALoop.__init__` <!-- id: 5 -->
- [x] Implement `_install_mandatory_passthrough(self, mandatory)` method on `TinyCUALoop` <!-- id: 6 -->
- [x] Implement `_clear_mandatory_passthrough(self)` method on `TinyCUALoop` <!-- id: 7 -->
- [x] Implement `_find_result_reviewer(self)` method on `TinyCUALoop` — scan queue for `TinyCUAResultReviewerNode`; returns node or None — session check is in `_on_reviewer_open_question` <!-- id: 8 -->
- [x] Implement `_ensure_query_analyst_at_front(self)` method on `TinyCUALoop` — restart queue to QueryAnalyst when passthrough is pending <!-- id: 8b -->
- [x] Update `run()` to call `_ensure_query_analyst_at_front()` when `_pending_mandatory_passthrough` is set <!-- id: 8c -->
- [x] Update `_on_reviewer_open_question(self, active_task)` from log-only stub to install MandatoryPassthrough <!-- id: 9 -->
- [x] Update `_execute_decision_node()` to inject `_pending_mandatory_passthrough` into QueryAnalyst input metadata before precheck <!-- id: 10 -->
- [x] Update `_execute_decision_node()` to call `_clear_mandatory_passthrough()` after successful passthrough forward <!-- id: 11 -->

## Testing Phase

- [x] Run all new tests — expect GREEN (all pass) <!-- id: 12 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` — confirm no regressions <!-- id: 13 -->

## Verification Phase

- [x] Verify `_on_reviewer_open_question` installs passthrough with correct `target_node_id` and `target_session_id` <!-- id: 14 -->
- [x] Verify stale passthrough (session mismatch) falls back to LLM classification <!-- id: 15 -->
- [x] Verify active task is preserved (not mutated) during passthrough cycle <!-- id: 16 -->
- [x] Verify passthrough is cleared after successful forward — no stale re-use <!-- id: 17 -->
- [x] Verify no-active-task edge case: `_on_reviewer_open_question(None)` does not install passthrough <!-- id: 17d -->
- [x] Verify queue restart: `_ensure_query_analyst_at_front` places QueryAnalyst at items[0] when passthrough is pending <!-- id: 17b -->
- [x] Verify two-call flow: first `run()` with open_question → second `run()` with continuation detects and consumes passthrough <!-- id: 17c -->
- [x] Verify user restart bypasses pending passthrough: new top-level query enters normal QueryAnalyst classification <!-- id: 17e -->

## Documentation Phase

- [x] Update spec.md Status Tracker — mark completed items <!-- id: 18 -->

## Review and Merge

- [x] Create pull request <!-- id: 19 --> (PR #111)
- [x] Address review feedback <!-- id: 20 --> (21+ review cycles completed)
- [ ] Merge to main branch <!-- id: 21 --> (pending final review approval)

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-11 (review-revision-2)*
