# Tasks: TINYCUA Review-Loop Hardening

Implementation tasks for TINYCUA Review-Loop Hardening. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write unit test for FR-1: `test_replan_threshold_default_is_three` + `test_replan_threshold_explicit_override_wins` in `test_worker_runtime_controller.py` <!-- id: 0 -->
- [ ] Write unit tests for FR-2: `TestSingleDecisionValidator` in new `test_review_single_decision.py` (two-decisions rejected, one accepted, one+task_update accepted, non-reviewer skipped, failed-decision not counted) <!-- id: 1 -->
- [ ] Write integration tests for FR-3: `test_list_files_tree_format_shows_directory_grouping` + `test_list_files_tree_empty_workspace` in `test_native_tools_files.py` <!-- id: 2 -->
- [ ] Write integration tests for FR-4: `test_read_file_not_found_with_close_match_returns_suggestion` + `test_read_file_not_found_no_close_match_plain_error` in `test_native_tools_files.py` <!-- id: 3 -->
- [ ] Update existing `test_auto_replan.py`: split `test_5_consecutive_rejections_trigger_replan` → `test_3_consecutive_rejections_trigger_replan`; `test_4_consecutive_rejections_still_retry` → `test_2_consecutive_rejections_still_retry` <!-- id: 4 -->
- [ ] Update existing `test_replan_loop_regression.py`: split tests into default-threshold (3) and explicit-threshold (5) variants where they currently pass `replan_threshold=5` to test default behavior <!-- id: 5 -->
- [ ] Update existing `test_native_tools_files.py` list_files tests: change `isinstance(result, list)` → `isinstance(result, str)` assertions <!-- id: 6 -->
- [ ] Run new + updated tests — expect RED (failures) since no implementation yet <!-- id: 7 -->

## Implementation Phase

- [ ] FR-1: change `replan_threshold` default `5 → 3` in `worker_runtime.py` `WorkerRuntimeController` dataclass <!-- id: 8 -->
- [ ] FR-2: add `_validate_result_reviewer_single_decision` validator in `validation_retry_mixin.py`; wire into `_validate_node_result` chain <!-- id: 9 -->
  - [ ] Count successful `task_review_decision` calls in `tool_results`
  - [ ] Reject if >1, with the named error message
  - [ ] Skip non-reviewer nodes; don't count `success=False` calls
- [ ] FR-3: change `list_files` in `files.py` to return a tree-formatted string (group by directory, full relative paths) <!-- id: 10 -->
  - [ ] Add tree-formatter helper (group entries by parent directory, indent under headers)
  - [ ] Preserve recursive vs scoped walk behavior
  - [ ] Handle empty-workspace case
- [ ] FR-4: add `_suggest_closest_path` helper + wire into `_read_lines` not-found path in `files.py` <!-- id: 11 -->
  - [ ] Implement segment-edit-distance (≤2 → suggest)
  - [ ] Walk workspace root to build candidate file list
  - [ ] Add `suggestion` key to not-found error dict when close match exists; omit when not
  - [ ] Never suggest the workspace root as a file

## Testing Phase

- [ ] Run new + updated tests — expect GREEN (all pass) <!-- id: 12 -->
- [ ] Write any additional unit tests surfaced during implementation <!-- id: 13 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 14 -->
- [ ] Run lint: `cd src/tinycua && uv run ruff check .` <!-- id: 15 -->

## Verification Phase

- [ ] Confirm no regressions in existing reviewer/replan integration tests <!-- id: 16 -->
- [ ] Spot-check single-decision error message is actionable for the model <!-- id: 17 -->
- [ ] Confirm `list_files` tree output is human-readable (model-readability proxy) <!-- id: 18 -->

## Documentation Phase

- [ ] Update spec/design if any drift from implementation is discovered <!-- id: 19 -->
- [ ] Note the Exp2 trade-off in any changelog/notes if applicable <!-- id: 20 -->

## Review and Merge

- [ ] Update PR #147 body: state this PR now implements the spec (not just spec+design), update How to Test with actual test commands <!-- id: 21 -->
- [ ] Address review feedback <!-- id: 22 -->
- [ ] Merge to `feat/tinycua-research-prototype` <!-- id: 23 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-26*