# Tasks: Custom Loop Types (M2)

Implementation tasks for M2 Custom Loop Types. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (defined in implementation-plan.md) <!-- id: 1 -->
- [ ] Write shared test fixtures in `tests/unit/loops/conftest.py` <!-- id: 2 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 3 -->

## Implementation Phase

### Phase 1 — Foundation

- [ ] Create `tinycua/loops/` package with `__init__.py` <!-- id: 4 -->
  - [ ] Create `tinycua/loops/` directory
  - [ ] Create `__init__.py` with re-exports
- [ ] Implement `LoopType` enum in `types.py` <!-- id: 5 -->
  - [ ] Define `LoopType(Enum)` with four values
  - [ ] Add string value for each enum member
- [ ] Implement `create_loop()` factory in `factory.py` <!-- id: 6 -->
  - [ ] Map each `LoopType` to its subclass constructor
  - [ ] Handle unknown type with `ValueError`
  - [ ] Forward `**kwargs` to loop constructors
- [ ] Write unit tests for enum values, factory mapping, error cases <!-- id: 7 -->
- [ ] Write integration test skeleton for factory <!-- id: 8 -->

### Phase 2 — ClassificationLoop

- [ ] Implement `ClassificationLoop` in `classification.py` extending `BaseLoop` <!-- id: 9 -->
  - [ ] Implement `__init__` with `rubric_dimensions`, `confidence_threshold`
  - [ ] Implement `run()` accepting `user_query`, `session_context`, `chat_history`
  - [ ] Implement score-based classification rubric (complexity + context-dependency)
  - [ ] Produce `ContextEnhancedQuery` + `ModeDecision` output
  - [ ] Handle edge cases: empty context, LLM failure, max iterations
- [ ] Write unit tests: mock LLM, verify output shape, edge cases (empty context) <!-- id: 10 -->
- [ ] Write integration test: real LLM call with known query/context <!-- id: 11 -->

### Phase 3 — ExplorationLoop

- [ ] Implement `ExplorationLoop` in `exploration.py` extending `BaseLoop` <!-- id: 12 -->
  - [ ] Implement `__init__` with `max_search_iterations`, `relevance_threshold`
  - [ ] Implement gap identification → search → relevance judging → compilation loop
  - [ ] Integrate with injected retrieval tool (duck-typed)
  - [ ] Produce `DigestedInformation` output
  - [ ] Handle edge cases: no relevant context, max iterations reached
- [ ] Write unit tests: mock retrieval tool, verify `DigestedInformation` output <!-- id: 13 -->
- [ ] Write integration test: real LLM + mock retrieval tool <!-- id: 14 -->

### Phase 4 — LinearAgentLoop

- [ ] Implement `LinearAgentLoop` in `linear_agent.py` extending `BaseLoop` <!-- id: 15 -->
  - [ ] Implement `__init__` with `system_prompt_template`, `shallow_task_list`
  - [ ] Implement ReAct pattern (think → act → observe → repeat)
  - [ ] Support configurable tool sets via constructor
  - [ ] Support `shallow_task_list` parameter for scope awareness
  - [ ] Handle edge cases: max iterations reached, tool call failures
- [ ] Write unit tests: mock tools, verify ReAct iteration, tool calling <!-- id: 16 -->
- [ ] Write integration test: real LLM + real tools <!-- id: 17 -->

### Phase 5 — HybridReviewLoop

- [ ] Implement `HybridReviewLoop` in `hybrid_review.py` extending `BaseLoop` <!-- id: 18 -->
  - [ ] Implement `__init__` with `deterministic_checks`, `consecutive_failure_threshold`
  - [ ] Implement `CheckResult` dataclass
  - [ ] Implement deterministic check execution loop (short-circuit on failure)
  - [ ] Implement LLM semantic review with fallback on deterministic failure
  - [ ] Produce `ReviewerDecision` with context updates and retry instructions
  - [ ] Handle edge cases: all checks pass, LLM call fails mid-review, contradictory LLM vs deterministic verdict
- [ ] Write unit tests: short-circuit on deterministic failure, all four decision statuses <!-- id: 19 -->
- [ ] Write integration test: real LLM + deterministic checks <!-- id: 20 -->

### Phase 6 — Tinycua Package Integration

- [ ] Modify `tinycua/__init__.py` to re-export `tinycua.loops` <!-- id: 21 -->
- [ ] Verify `tinycua.loops` is importable: `uv run python -c "from tinycua.loops import LoopType, create_loop"` <!-- id: 22 -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 23 -->
- [ ] Run unit tests with coverage: `cd src/tinycua && uv run pytest --cov=tinycua.loops` <!-- id: 24 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 25 -->
- [ ] Verify >85% unit test coverage on `tinycua.loops` module <!-- id: 26 -->
- [ ] Run all existing SDK tests (no regressions): `cd src/tinycua-sdk && uv run pytest` <!-- id: 27 -->
- [ ] Run all existing M1 state tests: `cd src/tinycua && uv run pytest tests/unit/state/` <!-- id: 28 -->

## Verification Phase

- [ ] Verify all loop types support sync + stream execution paths <!-- id: 29 -->
- [ ] Manual: verify `create_loop()` instantiates correct subclass for all four types <!-- id: 30 -->
- [ ] Manual: verify `ClassificationLoop` produces valid output with varied queries <!-- id: 31 -->
- [ ] Manual: verify `HybridReviewLoop` deterministic checks catch known-bad inputs <!-- id: 32 -->

## Documentation Phase

- [ ] Add docstrings to all public classes, methods, and functions <!-- id: 33 -->
- [ ] Update `tinycua/loops/__init__.py` with module docstring listing public API <!-- id: 34 -->
- [ ] Update changelog with M2 loops feature <!-- id: 35 -->

## Review and Merge

- [ ] Review implementation against spec requirements (FR-001 to FR-022) <!-- id: 36 -->
- [ ] Address review feedback <!-- id: 37 -->
- [ ] Squash and merge to main branch <!-- id: 38 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-31*
