# Tasks: End-to-End Architecture Verification Gate

Implementation tasks for the TinyCUA Architecture Verification Gate. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for the verification gate (see implementation-plan.md) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Create `tests/verification/__init__.py` package init <!-- id: 2 -->
- [ ] Create `tests/verification/config.py` — GateConfig that wraps LocalModelConfig and adds verification-specific defaults <!-- id: 3 -->
  - [ ] Read `OPENAI_CHAT_COMPLETIONS_BASE_URL`, `OPENAI_CHAT_COMPLETIONS_MODEL`, `OPENAI_CHAT_COMPLETIONS_API_KEY` <!-- id: 3a -->
  - [ ] Construct `LocalModelConfig` (from `tinycua.config.local_model`) with same parameters as production <!-- id: 3b -->
  - [ ] Wrap `LocalModelConfig` in `GateConfig` with verification-specific defaults (timeout, output_dir) <!-- id: 3c -->
- [ ] Create `tests/verification/paths.py` — define all 12 architecture paths <!-- id: 4 -->
  - [ ] Path 1: Passthrough (Simple) — QueryAnalyst → PrimaryAgent → Response <!-- id: 4a -->
  - [ ] Path 2: Passthrough with Digestion — QueryAnalyst → PrimaryAgent → InformationDigester → PrimaryAgent → Response <!-- id: 4b -->
  - [ ] Path 3: Worker (Simple) — QueryAnalyst → InformationDigester → Worker → TaskCreation → TaskExecutor → ResultReviewer → PrimaryAgent → Response <!-- id: 4c -->
  - [ ] Path 4: Worker with Task Creation — includes TaskAssessor → TaskAnalyzer <!-- id: 4d -->
  - [ ] Path 5: Worker with Retry — ResultReviewer(retry) → TaskExecutor <!-- id: 4e -->
  - [ ] Path 6: Worker with Replan — ResultReviewer(replan) → TaskAnalyzer → TaskExecutor <!-- id: 4f -->
  - [ ] Path 7: Worker with Failure — ResultReviewer(failure threshold), Worker stays active <!-- id: 4g -->
  - [ ] Path 8: Worker with Task Decomposition — TaskAssessor(decompose) → TaskAnalyzer <!-- id: 4h -->
  - [ ] Path 9: Worker Re-entry with Task Recreation — task_recreation classification <!-- id: 4i -->
  - [ ] Path 10: Worker Re-entry with Task Reanalysis — task_reanalysis classification <!-- id: 4j -->
  - [ ] Path 11: Worker Re-entry with Proceed Execution — proceed_execution classification <!-- id: 4k -->
  - [ ] Path 12: Worker Result Aggregation — includes ResultAggregationNode <!-- id: 4l -->
  - [ ] Create path registry with lookup by name <!-- id: 4m -->
- [ ] Create `tests/verification/executor.py` — PathExecutor using NodeQueue <!-- id: 5 -->
  - [ ] Instantiate actual TinyCUA node classes from path.node_sequence <!-- id: 5a -->
  - [ ] Build NodeQueue with instantiated nodes <!-- id: 5b -->
  - [ ] Run NodeQueue and capture node outputs, session state, LLM interactions <!-- id: 5c -->
  - [ ] Implement per-path timeout controller <!-- id: 5d -->
  - [ ] Implement LLM interaction logging for all paths <!-- id: 5e -->
  - [ ] Validate final state against path.expected_outcome <!-- id: 5f -->
- [ ] Create `tests/verification/reporter.py` — ReportGenerator <!-- id: 6 -->
  - [ ] Implement JSON output format with all VerificationReport fields <!-- id: 6a -->
  - [ ] Implement human-readable summary report <!-- id: 6b -->
  - [ ] Include per-path status, duration, and error details <!-- id: 6c -->
- [ ] Create `tests/verification/gate.py` — VerificationGate orchestrator <!-- id: 7 -->
  - [ ] Implement `run_all()` — run all 12 paths sequentially <!-- id: 7a -->
  - [ ] Implement `run_path(name)` — run single path by name <!-- id: 7b -->
  - [ ] Implement `run_paths(names)` — run specific paths <!-- id: 7c -->
  - [ ] Aggregate results into VerificationReport <!-- id: 7d -->
  - [ ] Determine overall pass/fail (all paths must pass) <!-- id: 7e -->
- [ ] Create `tests/verification/cross_cutting.py` — cross-cutting concern verification <!-- id: 8 -->
  - [ ] Hook into node execution lifecycle to record tool invocations <!-- id: 8a -->
  - [ ] Verify context propagation between tasks <!-- id: 8b -->
  - [ ] Verify no duplicate context (dedupe) <!-- id: 8c -->
  - [ ] Verify tool scoping per NodeToolPolicy <!-- id: 8d -->
  - [ ] Verify retry creates new sub-session with failure context <!-- id: 8e -->
  - [ ] Verify output validation is called on every node response <!-- id: 8f -->
- [ ] Create `tests/verification/test_gate.py` — pytest entry point <!-- id: 9 -->
  - [ ] Parameterized test for all 12 paths <!-- id: 9a -->
  - [ ] Individual path execution test <!-- id: 9b -->
  - [ ] JSON output validation test <!-- id: 9c -->
  - [ ] Human-readable summary test <!-- id: 9d -->
  - [ ] LLM interaction log test <!-- id: 9e -->
  - [ ] Timeout handling test <!-- id: 9f -->
  - [ ] LLM unavailable graceful failure test <!-- id: 9g -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all 12 paths pass) <!-- id: 10 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` — confirm no regressions <!-- id: 11 -->

## Verification Phase

- [ ] Run verification gate against local LLM and confirm all 12 paths pass <!-- id: 12 -->
- [ ] Verify JSON output is well-formed and contains all expected fields <!-- id: 13 -->
- [ ] Verify human-readable report is clear and actionable <!-- id: 14 -->
- [ ] Test failure reporting by temporarily misconfiguring a path <!-- id: 15 -->
- [ ] Verify individual path execution works for targeted debugging <!-- id: 16 -->

## Documentation Phase

- [ ] Update spec.md status tracker — mark completed items <!-- id: 17 -->

## Review and Merge

- [ ] Create pull request <!-- id: 18 -->
- [ ] Address review feedback <!-- id: 19 -->
- [ ] Merge to main branch <!-- id: 20 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-13*
