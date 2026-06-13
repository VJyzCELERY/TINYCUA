# Tasks: End-to-End Architecture Verification Gate

Implementation tasks for the TinyCUA Architecture Verification Gate. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests for the verification gate (see implementation-plan.md) <!-- id: 0 -->
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [x] Create `tests/verification/__init__.py` package init <!-- id: 2 -->
- [x] Create `tests/verification/config.py` — GateConfig that wraps LocalModelConfig and adds verification-specific defaults <!-- id: 3 -->
  - [x] Read `OPENAI_CHAT_COMPLETIONS_BASE_URL`, `OPENAI_CHAT_COMPLETIONS_MODEL`, `OPENAI_CHAT_COMPLETIONS_API_KEY` <!-- id: 3a -->
  - [x] Construct `LocalModelConfig` (from `tinycua.config.local_model`) with same parameters as production <!-- id: 3b -->
  - [x] Wrap `LocalModelConfig` in `GateConfig` with verification-specific defaults (timeout, output_dir) <!-- id: 3c -->
- [x] Create `tests/verification/paths.py` — define all 12 architecture paths <!-- id: 4 -->
  - [x] Path 1: Passthrough (Simple) — QueryAnalyst → PrimaryAgent → Response <!-- id: 4a -->
  - [x] Path 2: Passthrough with Digestion — QueryAnalyst → PrimaryAgent → InformationDigester → PrimaryAgent → Response <!-- id: 4b -->
  - [x] Path 3: Worker (Simple) — QueryAnalyst → InformationDigester → Worker → TaskCreation → TaskExecutor → ResultReviewer → PrimaryAgent → Response <!-- id: 4c -->
  - [x] Path 4: Worker with Task Creation — includes TaskAssessor → TaskAnalyzer <!-- id: 4d -->
  - [x] Path 5: Worker with Retry — ResultReviewer(retry) → TaskExecutor <!-- id: 4e -->
  - [x] Path 6: Worker with Replan — ResultReviewer(replan) → TaskAnalyzer → TaskExecutor <!-- id: 4f -->
  - [x] Path 7: Worker with Failure — ResultReviewer(failure threshold), Worker stays active <!-- id: 4g -->
  - [x] Path 8: Worker with Task Decomposition — TaskAssessor(decompose) → TaskAnalyzer <!-- id: 4h -->
  - [x] Path 9: Worker Re-entry with Task Recreation — task_recreation classification <!-- id: 4i -->
  - [x] Path 10: Worker Re-entry with Task Reanalysis — task_reanalysis classification <!-- id: 4j -->
  - [x] Path 11: Worker Re-entry with Proceed Execution — proceed_execution classification <!-- id: 4k -->
  - [x] Path 12: Worker Result Aggregation — includes ResultAggregationNode <!-- id: 4l -->
  - [x] Create path registry with lookup by name <!-- id: 4m -->
- [x] Create `tests/verification/executor.py` — PathExecutor using NodeQueue <!-- id: 5 -->
  - [x] Instantiate actual TinyCUA node classes from path.node_sequence <!-- id: 5a -->
  - [x] Build NodeQueue with instantiated nodes <!-- id: 5b -->
  - [x] Run NodeQueue and capture node outputs, session state, LLM interactions <!-- id: 5c -->
  - [x] Implement per-path timeout controller <!-- id: 5d -->
  - [x] Implement LLM interaction logging for all paths <!-- id: 5e -->
  - [x] Validate final state against path.expected_outcome <!-- id: 5f -->
- [x] Create `tests/verification/reporter.py` — ReportGenerator <!-- id: 6 -->
  - [x] Implement JSON output format with all VerificationReport fields <!-- id: 6a -->
  - [x] Implement human-readable summary report <!-- id: 6b -->
  - [x] Include per-path status, duration, and error details <!-- id: 6c -->
- [x] Create `tests/verification/gate.py` — VerificationGate orchestrator <!-- id: 7 -->
  - [x] Implement `run_all()` — run all 12 paths sequentially <!-- id: 7a -->
  - [x] Implement `run_path(name)` — run single path by name <!-- id: 7b -->
  - [x] Implement `run_paths(names)` — run specific paths <!-- id: 7c -->
  - [x] Aggregate results into VerificationReport <!-- id: 7d -->
  - [x] Determine overall pass/fail (all paths must pass) <!-- id: 7e -->
- [x] Create `tests/verification/cross_cutting.py` — cross-cutting concern verification <!-- id: 8 -->
  - [x] Hook into node execution lifecycle to record tool invocations <!-- id: 8a -->
  - [x] Verify context propagation between tasks <!-- id: 8b -->
  - [x] Verify no duplicate context (dedupe) <!-- id: 8c -->
  - [x] Verify tool scoping per NodeToolPolicy <!-- id: 8d -->
  - [x] Verify retry creates new sub-session with failure context <!-- id: 8e -->
  - [x] Verify output validation is called on every node response <!-- id: 8f -->
- [x] Create `tests/verification/test_gate.py` — pytest entry point <!-- id: 9 -->
  - [x] Parameterized test for all 12 paths <!-- id: 9a -->
  - [x] Individual path execution test <!-- id: 9b -->
  - [x] JSON output validation test <!-- id: 9c -->
  - [x] Human-readable summary test <!-- id: 9d -->
  - [x] LLM interaction log test <!-- id: 9e -->
  - [x] Timeout handling test <!-- id: 9f -->
  - [x] LLM unavailable graceful failure test <!-- id: 9g -->

## Testing Phase

- [x] Run integration tests — expect GREEN (all 12 paths pass) <!-- id: 10 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` — confirm no regressions <!-- id: 11 -->

## Verification Phase

- [x] Run verification gate against local LLM and confirm all 12 paths pass <!-- id: 12 -->
- [x] Verify JSON output is well-formed and contains all expected fields <!-- id: 13 -->
- [x] Verify human-readable report is clear and actionable <!-- id: 14 -->
- [ ] Test failure reporting by temporarily misconfiguring a path <!-- id: 15 -->
- [x] Verify individual path execution works for targeted debugging <!-- id: 16 -->

## Documentation Phase

- [x] Update spec.md status tracker — mark completed items <!-- id: 17 -->

## Review and Merge

- [x] Create pull request <!-- id: 18 -->
- [x] Address review feedback <!-- id: 19 -->
- [ ] Merge to main branch <!-- id: 20 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-13*
