# Tasks: TinyCUATaskAssessorNode

Implementation tasks for TinyCUATaskAssessorNode. Check off items as completed.

> **Note**: Phase 1 (MVP) is complete — all tasks below are checked. Phase 2 is deferred.

## TDD Phase (Tests First)

- [x] Write unit tests for TinyCUATaskAssessorNode initialization <!-- id: 0 -->
- [x] Write unit tests for `__call__` with various task tree states <!-- id: 1 -->
- [x] Write unit tests for `on_complete` queue advancement <!-- id: 2 -->
- [x] Write integration tests for AnalysisEffortNode → TaskAssessor flow <!-- id: 3 -->
- [x] Run all tests — expect RED (before implementation) <!-- id: 4 -->

## Implementation Phase

- [x] Create `TinyCUATaskAssessorNode` class in `tinycua/loops/task_assessor.py` <!-- id: 5 -->
  - [x] Implement `__init__` with node_id, config, mode parameters
  - [x] Implement `__call__` with LLM delegation and JSON response parsing
  - [x] Implement `on_complete` with queue advancement logic (skip analyzer when no tasks)
  - [x] Add logging for selected tasks and mode
- [x] Export `TinyCUATaskAssessorNode` in `tinycua/loops/__init__.py` <!-- id: 6 -->
- [x] Verify `AnalysisEffortNode._prepend_assessor_analyzer_pair` creates TaskAssessor instances <!-- id: 7 -->

## Testing Phase

- [x] Run unit tests — expect GREEN (all 10 pass) <!-- id: 8 -->
- [x] Run integration tests — expect GREEN (5 pass) <!-- id: 9 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 10 -->

## Verification Phase

- [x] Verify TaskAssessor handles empty task tree gracefully <!-- id: 11 -->
- [x] Verify TaskAssessor handles malformed LLM responses with warning <!-- id: 12 -->
- [x] Verify on_complete skips TaskAnalyzer when no tasks selected <!-- id: 13 -->
- [x] Verify on_complete advances queue normally when tasks selected <!-- id: 14 -->

## Documentation Phase

- [x] Write spec.md for Milestone 2.7 <!-- id: 15 -->
- [x] Write design.md for Milestone 2.7 <!-- id: 16 -->
- [x] Write implementation-plan.md <!-- id: 17 -->
- [x] Write task.md (this file) <!-- id: 18 -->

## Review and Merge

- [ ] Address review feedback on PR #107 <!-- id: 19 -->
- [ ] Merge to base branch <!-- id: 20 -->

## Phase 2 — Deferred Tasks (NOT in this PR)

- [ ] Implement reviewer-replan mode for local-region assessment <!-- id: 21 -->
- [ ] Create `TinyCUATaskAssessorNodeConfig` with `assessment_schema` <!-- id: 22 -->
- [ ] Add structured assessment output via `assessment_schema` <!-- id: 23 -->
- [ ] Add task status update capabilities during assessment <!-- id: 24 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-10*
