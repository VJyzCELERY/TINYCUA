# Tasks: Stage 2.5 — Clear Backward Compatibility

Implementation tasks for clearing backward-compatibility artifacts. Check off items as completed.

## Implementation Phase

- [x] Update Stage 2 design.md — remove `_OBSOLETE_PARAMS` frozenset, `**kwargs` validation loop, and obsolete-params error scenario <!-- id: 1 -->
- [x] Update Stage 2 spec.md — remove obsolete-param requirement subsection and success criterion <!-- id: 2 -->
- [x] Update Stage 2 targets.md — remove Target 2.5 entry, renumber 2.6→2.5, 2.7→2.6 <!-- id: 3 -->
- [x] Delete `targets/05_obsolete_params_rejected.py` and its expected-output file <!-- id: 4 -->
- [x] Remove `_OBSOLETE_PARAMS` references from Stage 0 files (spec.md, design.md, implementation-plan.md, task.md) <!-- id: 5 -->
- [x] Update Stage 3 description.md — add Stage 2.5 to dependencies <!-- id: 6 -->
- [x] Update Stage 9 design.md — remove obsolete-param test strategy row <!-- id: 7 -->
- [x] Update ROADMAP.md — add Stage 2.5, clean Stage 0 deletions, reframe as project reset <!-- id: 8 -->
- [x] Create verification target `targets/01_no_obsolete_params.py` <!-- id: 9 -->

## Testing Phase

- [x] Run verification target: `uv run python targets/01_no_obsolete_params.py` → expect PASS <!-- id: 10 -->
- [x] Run `grep -r "_OBSOLETE_PARAMS" specs/refactor-tinycua-sdk-v2/` → expect no matches outside Stage 2.5 and historical report <!-- id: 11 -->
- [x] Verify `05_obsolete_params_rejected.py` target files are deleted <!-- id: 12 -->

## Verification Phase

- [x] Check all Stage 3–9 docs for remaining "v2 migration" or "backward-compat" language <!-- id: 13 -->
- [x] Verify ROADMAP renders correctly with Stage 2.5 between Stage 2 and Stage 3 <!-- id: 14 -->

## Documentation Phase

- [x] Update any cross-references to renumbered targets (2.6→2.5, 2.7→2.6) <!-- id: 15 -->
- [x] Ensure task.md and implementation-plan.md are consistent with actual changes <!-- id: 16 -->

## Review and Merge

- [x] Review all changes for completeness (did we miss any backward-compat references?) <!-- id: 17 -->
- [ ] Merge Stage 2.5 branch before starting significant Stage 3+ work to avoid ROADMAP conflicts <!-- id: 18 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-05-06*
