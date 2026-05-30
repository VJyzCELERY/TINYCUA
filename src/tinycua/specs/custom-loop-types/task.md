# Tasks: Custom Loop Types (M2)

Implementation tasks for M2 Custom Loop Types. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests (defined in implementation-plan.md) <!-- id: 1 -->
- [x] Write shared test fixtures in `tests/unit/loops/conftest.py` <!-- id: 2 -->
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 3 -->

## Implementation Phase

### Phase 1 — Foundation

- [x] Create `tinycua/loops/` package with `__init__.py` <!-- id: 4 -->
  - [x] Create `tinycua/loops/` directory
  - [x] Create `__init__.py` with re-exports
- [x] Implement `LoopType` enum in `types.py` <!-- id: 5 -->
  - [x] Define `LoopType(Enum)` with four values
  - [x] Add string value for each enum member
- [x] Implement `create_loop()` factory in `factory.py` <!-- id: 6 -->
  - [x] Map each `LoopType` to its subclass constructor
  - [x] Handle unknown type with `ValueError`
  - [x] Forward `**kwargs` to loop constructors
- [x] Write unit tests for enum values, factory mapping, error cases <!-- id: 7 -->
- [x] Write integration test skeleton for factory <!-- id: 8 -->

### Phase 2 — ClassificationLoop

- [x] Implement `ClassificationLoop` in `classification.py` extending `BaseLoop` <!-- id: 9 -->
  - [x] Implement `__init__` with `rubric_dimensions`, `confidence_threshold`
  - [x] Implement `run()` accepting `user_query`, `session_context`, `chat_history`
  - [x] Implement score-based classification rubric (complexity + context-dependency)
  - [x] Produce `ContextEnhancedQuery` + `ModeDecision` output
  - [x] Handle edge cases: empty context, LLM failure, max iterations
- [x] Write unit tests: mock LLM, verify output shape, edge cases (empty context) <!-- id: 10 -->
- [x] Write integration test: real LLM call with known query/context <!-- id: 11 -->

### Phase 3 — ExplorationLoop

- [x] Implement `ExplorationLoop` in `exploration.py` extending `BaseLoop` <!-- id: 12 -->
  - [x] Implement `__init__` with `max_search_iterations`, `relevance_threshold`
  - [x] Implement gap identification → search → relevance judging → compilation loop
  - [x] Integrate with injected retrieval tool (duck-typed)
  - [x] Produce `DigestedInformation` output
  - [x] Handle edge cases: no relevant context, max iterations reached
- [x] Write unit tests: mock retrieval tool, verify `DigestedInformation` output <!-- id: 13 -->
- [x] Write integration test: real LLM + mock retrieval tool <!-- id: 14 -->

### Phase 4 — LinearAgentLoop

- [x] Implement `LinearAgentLoop` in `linear_agent.py` extending `BaseLoop` <!-- id: 15 -->
  - [x] Implement `__init__` with `system_prompt_template`, `shallow_task_list`
  - [x] Implement ReAct pattern (think → act → observe → repeat)
  - [x] Support configurable tool sets via constructor
  - [x] Support `shallow_task_list` parameter for scope awareness
  - [x] Handle edge cases: max iterations reached, tool call failures
- [x] Write unit tests: mock tools, verify ReAct iteration, tool calling <!-- id: 16 -->
- [x] Write integration test: real LLM + real tools <!-- id: 17 -->

### Phase 5 — HybridReviewLoop

- [x] Implement `HybridReviewLoop` in `hybrid_review.py` extending `BaseLoop` <!-- id: 18 -->
  - [x] Implement `__init__` with `deterministic_checks`, `consecutive_failure_threshold`
  - [x] Implement `CheckResult` dataclass
  - [x] Implement deterministic check execution loop (short-circuit on failure)
  - [x] Implement LLM semantic review with fallback on deterministic failure
  - [x] Produce `ReviewerDecision` with context updates and retry instructions
  - [x] Handle edge cases: all checks pass, LLM call fails mid-review, contradictory LLM vs deterministic verdict
- [x] Write unit tests: short-circuit on deterministic failure, all four decision statuses <!-- id: 19 -->
- [x] Write integration test: real LLM + deterministic checks <!-- id: 20 -->

### Phase 6 — Tinycua Package Integration

- [x] Modify `tinycua/__init__.py` to re-export `tinycua.loops` <!-- id: 21 -->
- [x] Verify `tinycua.loops` is importable: `uv run python -c "from tinycua.loops import LoopType, create_loop"` <!-- id: 22 -->

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 23 -->
- [x] Run unit tests with coverage: `cd src/tinycua && uv run pytest --cov=tinycua.loops` <!-- id: 24 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 25 -->
- [ ] Verify >85% unit test coverage on `tinycua.loops` module <!-- id: 26 -->
- [x] Run all existing SDK tests (no regressions): `cd src/tinycua-sdk && uv run pytest` <!-- id: 27 -->
- [x] Run all existing M1 state tests: `cd src/tinycua && uv run pytest tests/unit/state/` <!-- id: 28 -->

## Verification Phase

- [x] Verify all loop types support sync + stream execution paths <!-- id: 29 -->
- [x] Manual: verify `create_loop()` instantiates correct subclass for all four types <!-- id: 30 -->
- [x] Manual: verify `ClassificationLoop` produces valid output with varied queries <!-- id: 31 -->
- [x] Manual: verify `HybridReviewLoop` deterministic checks catch known-bad inputs <!-- id: 32 -->

## Documentation Phase

- [x] Add docstrings to all public classes, methods, and functions <!-- id: 33 -->
- [x] Update `tinycua/loops/__init__.py` with module docstring listing public API <!-- id: 34 -->
- [ ] Update changelog with M2 loops feature <!-- id: 35 -->

## Review and Merge

- [ ] Review implementation against spec requirements (FR-001 to FR-022) <!-- id: 36 -->
- [ ] Address review feedback <!-- id: 37 -->
- [ ] Squash and merge to main branch <!-- id: 38 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-31*
