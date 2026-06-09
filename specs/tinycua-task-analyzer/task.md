# Tasks: TinyCUATaskAnalyzerNode — Full Five-Mode Support

Implementation tasks for extending TinyCUATaskAnalyzerNode to support all five analysis modes. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for all five modes, tool scope, and task tree validation in `src/tinycua/tests/unit/test_task_analyzer_node.py` <!-- id: 0 -->
  - `test_task_analyzer_integration_with_tool_policy` — mode-dependent tool filtering across all modes (spec test 1)
  - `test_task_analyzer_lifecycle_hooks_in_queue` — queue-based lifecycle hooks fire correctly (spec test 2)
  - `test_task_analyzer_recreation_in_queue_receives_task_tools` — recreation mode in queue receives TaskInit/TaskCreate tools (spec test 3)
  - `test_task_analyzer_initial_analysis_in_queue_excludes_task_tools` — initial_analysis mode in queue excludes TaskInit/TaskCreate (spec test 4)
  - `test_task_analyzer_task_tree_validation_none_raises_error` — NodeExecutionError when task tree is None (spec test 5)
  - `test_task_analyzer_all_five_modes_are_valid` — all five modes accepted (unit)
  - `test_task_analyzer_recreation_allows_task_creation_tools` — recreation includes TaskInit/TaskCreate (unit)
  - `test_task_analyzer_non_recreation_excludes_task_creation_tools` — non-recreation excludes TaskInit/TaskCreate (unit)
  - `test_task_analyzer_invalid_mode_raises_value_error` — unknown modes raise ValueError (unit)
  - `test_task_analyzer_default_mode_is_initial_analysis` — default is initial_analysis (unit)
- [ ] Run integration tests — expect RED (failures) since implementation not yet updated <!-- id: 1 -->

## Implementation Phase

- [ ] Extend `_VALID_MODES` frozenset to include all five modes: `initial_analysis`, `recreation`, `reanalysis`, `effort_loop_decomposition`, `local_replan`. Remove `analysis` mode. <!-- id: 2 -->
  - [ ] Replace frozenset definition in `task_analyzer.py`
  - [ ] Verify no other modules reference the removed `analysis` mode
- [ ] Update `worker.py:_route_task_recreation()` to use `mode="recreation"` instead of `mode="analysis"` <!-- id: 3 -->
  - [ ] Change `mode="analysis"` to `mode="recreation"` at line 236
  - [ ] Update docstring to reflect `mode="recreation"`
- [ ] Update `_resolve_tool_scope()` to allow TaskInit/TaskCreate only in `recreation` mode <!-- id: 4 -->
  - [ ] Add `recreation` to the mode branching logic
  - [ ] Ensure all other modes exclude TaskInit/TaskCreate
- [ ] Add `_validate_task_tree_non_none()` method to check task tree after completion <!-- id: 5 -->
  - [ ] Import `NodeExecutionError` from `tinycua.loops.node`
  - [ ] Implement validation: check `session.task is not None`
  - [ ] Raise `NodeExecutionError` with descriptive message if task tree is `None`
- [ ] Call `_validate_task_tree_non_none()` at end of `__call__()` before returning <!-- id: 6 -->
  - [ ] Insert validation call after LLM result, before return
- [ ] Change default `mode` parameter from `"analysis"` to `"initial_analysis"` in constructor <!-- id: 7 -->
- [ ] Update class and module docstrings to document all five modes <!-- id: 8 -->
  - [ ] Document each mode's purpose and tool scoping
  - [ ] Remove references to legacy `analysis` mode (including worker.py call site)

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 9 -->
- [ ] Write unit tests for edge cases: empty input, None task tree, valid task tree <!-- id: 10 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 11 -->

## Verification Phase

- [ ] Verify `__call__` logs mode and completion status via `logger.info()` (existing logging from FR-007) <!-- id: 12 -->
- [ ] Verify `__call__` calls `super().__call__()` to inherit retry behavior from ProcessNode (FR-008) <!-- id: 13 -->
- [ ] Verify all five modes are accepted and documented <!-- id: 14 -->
- [ ] Verify `recreation` mode includes TaskInit/TaskCreate in tool scope <!-- id: 15 -->
- [ ] Verify all other modes exclude TaskInit/TaskCreate from tool scope <!-- id: 16 -->
- [ ] Verify `NodeExecutionError` is raised when task tree is `None` after completion <!-- id: 17 -->
- [ ] Verify `ValueError` is raised for unknown modes <!-- id: 18 -->

## Documentation Phase

- [ ] Update module docstring to reflect all five modes <!-- id: 19 -->
- [ ] Update class docstring with mode descriptions and tool scoping <!-- id: 20 -->

## Review and Merge

- [ ] Create pull request <!-- id: 21 -->
- [ ] Address review feedback <!-- id: 22 -->
- [ ] Merge to main branch <!-- id: 23 -->

---

## References

- Spec: `./spec.md`
- Design: `./design.md`
- Implementation Plan: `./implementation-plan.md`

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-10*
