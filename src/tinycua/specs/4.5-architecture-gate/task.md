# Tasks: End-to-End Architecture Verification Gate

Implementation tasks for the TinyCUA Architecture Verification Gate. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for the verification gate (see implementation-plan.md) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Create `tests/verification/__init__.py` package init <!-- id: 2 -->
- [ ] Create `tests/verification/config.py` — GateConfig that reads env vars and constructs SessionConfig <!-- id: 3 -->
  - [ ] Read `OPENAI_CHAT_COMPLETIONS_BASE_URL`, `OPENAI_CHAT_COMPLETIONS_MODEL`, `OPENAI_CHAT_COMPLETIONS_API_KEY`
  - [ ] Construct `SessionConfig` with same parameters as production
  - [ ] Support default timeout configuration
- [ ] Create `tests/verification/paths.py` — define all 12 architecture paths <!-- id: 4 -->
  - [ ] Path 1: Passthrough (Simple) — QueryAnalyst → PrimaryAgent → Response
  - [ ] Path 2: Passthrough with Digestion — QueryAnalyst → PrimaryAgent → InformationDigester → PrimaryAgent → Response
  - [ ] Path 3: Worker (Simple) — QueryAnalyst → InformationDigester → Worker → TaskCreation → TaskExecutor → ResultReviewer → PrimaryAgent → Response
  - [ ] Path 4: Worker with Task Creation — includes TaskAssessor → TaskAnalyzer
  - [ ] Path 5: Worker with Retry — ResultReviewer(retry) → TaskExecutor
  - [ ] Path 6: Worker with Replan — ResultReviewer(replan) → TaskAnalyzer → TaskExecutor
  - [ ] Path 7: Worker with Failure — ResultReviewer(failure threshold), Worker stays active
  - [ ] Path 8: Worker with Task Decomposition — TaskAssessor(decompose) → TaskAnalyzer
  - [ ] Path 9: Worker Re-entry with Task Recreation — task_recreation classification
  - [ ] Path 10: Worker Re-entry with Task Reanalysis — task_reanalysis classification
  - [ ] Path 11: Worker Re-entry with Proceed Execution — proceed_execution classification
  - [ ] Path 12: Worker Result Aggregation — includes ResultAggregationNode
  - [ ] Create path registry with lookup by name
- [ ] Create `tests/verification/executor.py` — PathExecutor using NodeQueue <!-- id: 5 -->
  - [ ] Instantiate actual TinyCUA node classes from path.node_sequence
  - [ ] Build NodeQueue with instantiated nodes
  - [ ] Run NodeQueue and capture node outputs, session state, LLM interactions
  - [ ] Implement per-path timeout controller
  - [ ] Implement LLM interaction logging for all paths
  - [ ] Validate final state against path.expected_outcome
- [ ] Create `tests/verification/reporter.py` — ReportGenerator <!-- id: 6 -->
  - [ ] Implement JSON output format with all VerificationReport fields
  - [ ] Implement human-readable summary report
  - [ ] Include per-path status, duration, and error details
- [ ] Create `tests/verification/gate.py` — VerificationGate orchestrator <!-- id: 7 -->
  - [ ] Implement `run_all()` — run all 12 paths sequentially
  - [ ] Implement `run_path(name)` — run single path by name
  - [ ] Implement `run_paths(names)` — run specific paths
  - [ ] Aggregate results into VerificationReport
  - [ ] Determine overall pass/fail (all paths must pass)
- [ ] Create `tests/verification/cross_cutting.py` — cross-cutting concern verification <!-- id: 8 -->
  - [ ] Hook into node execution lifecycle to record tool invocations
  - [ ] Verify context propagation between tasks
  - [ ] Verify no duplicate context (dedupe)
  - [ ] Verify tool scoping per NodeToolPolicy
  - [ ] Verify retry creates new sub-session with failure context
  - [ ] Verify output validation is called on every node response
- [ ] Create `tests/verification/test_gate.py` — pytest entry point <!-- id: 9 -->
  - [ ] Parameterized test for all 12 paths
  - [ ] Individual path execution test
  - [ ] JSON output validation test
  - [ ] Human-readable summary test
  - [ ] LLM interaction log test
  - [ ] Timeout handling test
  - [ ] LLM unavailable graceful failure test

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
