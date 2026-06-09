# Tasks: TinyCUATaskAnalyzerNode — Full Five-Mode Support

Implementation tasks for extending TinyCUATaskAnalyzerNode to support all five analysis modes. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for all five modes, tool scope, and task tree validation in `src/tinycua/tests/unit/test_task_analyzer_node.py` <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since implementation not yet updated <!-- id: 1 -->

## Implementation Phase

- [ ] Extend `_VALID_MODES` frozenset to include all five modes: `initial_analysis`, `recreation`, `reanalysis`, `effort_loop_decomposition`, `local_replan`. Remove `analysis` mode. <!-- id: 2 -->
  - [ ] Replace frozenset definition in `task_analyzer.py`
  - [ ] Verify no other modules reference the removed `analysis` mode
- [ ] Update `_resolve_tool_scope()` to allow TaskInit/TaskCreate only in `recreation` mode <!-- id: 3 -->
  - [ ] Add `recreation` to the mode branching logic
  - [ ] Ensure all other modes exclude TaskInit/TaskCreate
- [ ] Add `_validate_task_tree_non_none()` method to check task tree after completion <!-- id: 4 -->
  - [ ] Import `NodeExecutionError` from `tinycua.loops.node`
  - [ ] Implement validation: check `session.task is not None`
  - [ ] Raise `NodeExecutionError` with descriptive message if task tree is `None`
- [ ] Call `_validate_task_tree_non_none()` at end of `__call__()` before returning <!-- id: 5 -->
  - [ ] Insert validation call after LLM result, before return
- [ ] Change default `mode` parameter from `"analysis"` to `"initial_analysis"` in constructor <!-- id: 6 -->
- [ ] Update class and module docstrings to document all five modes <!-- id: 7 -->
  - [ ] Document each mode's purpose and tool scoping
  - [ ] Remove references to legacy `analysis` mode

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 8 -->
- [ ] Write unit tests for edge cases: empty input, None task tree, valid task tree <!-- id: 9 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 10 -->

## Verification Phase

- [ ] Verify all five modes are accepted and documented <!-- id: 11 -->
- [ ] Verify `recreation` mode includes TaskInit/TaskCreate in tool scope <!-- id: 12 -->
- [ ] Verify all other modes exclude TaskInit/TaskCreate from tool scope <!-- id: 13 -->
- [ ] Verify `NodeExecutionError` is raised when task tree is `None` after completion <!-- id: 14 -->
- [ ] Verify `ValueError` is raised for unknown modes <!-- id: 15 -->

## Documentation Phase

- [ ] Update module docstring to reflect all five modes <!-- id: 16 -->
- [ ] Update class docstring with mode descriptions and tool scoping <!-- id: 17 -->

## Review and Merge

- [ ] Create pull request <!-- id: 18 -->
- [ ] Address review feedback <!-- id: 19 -->
- [ ] Merge to main branch <!-- id: 20 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-10*
