# Implementation: Custom Loop Types (M2)

Implement four canonical custom loop types — Classification, Exploration, Linear Agent, and Hybrid Review — as `BaseLoop` subclasses in a new `tinycua.loops` module. Each loop type bridges M1 State Objects (typed data) with the SDK's `BaseLoop` (execution foundation), giving each TINYCUA agent a dedicated, testable loop implementation.

## Context

- **Spec Reference**: `src/tinycua/specs/custom-loop-types/spec.md`
- **Design Reference**: `src/tinycua/specs/custom-loop-types/design.md`
- **Priority**: P0
- **Estimated Effort**: L

## Environment Pre-requisites

> N/A — This implementation is code-only with no external service dependencies. All tests use mocks or the SDK's standard integration mock.

---

## Success Criteria — Integration Tests (TDD First)

The following integration tests prove the feature works. They are written **FIRST** — before any implementation code. Implementation is only complete when these tests pass.

> Note: `integration` markers in `pyproject.toml` indicate tests requiring a local LLM server. For automated CI, these run against the SDK's standard integration mock (`pytest-httpx` or in-memory provider).

```python
# Test file: tests/integration/test_custom_loops.py
"""Integration tests for custom loop types (M2)."""

import pytest
from tinycua.loops import (
    LoopType,
    create_loop,
    ClassificationLoop,
    ExplorationLoop,
    LinearAgentLoop,
    HybridReviewLoop,
)


@pytest.mark.integration
async def test_classification_loop_full_flow(mock_agent, mock_llm, sample_session_context):
    """Given a ClassificationLoop with rubric parameters, When run() is called
    with a user query and session context, Then the loop produces a ModeDecision
    (with valid mode, score, confidence, reasons) and a ContextEnhancedQuery string."""
    loop = ClassificationLoop(rubric_dimensions=["complexity", "context_dependency"])
    result = await loop.run(
        agent=mock_agent,
        messages=[],
        tools=[],
        user_query="What is the status of project X?",
        session_context=sample_session_context,
        chat_history=[],
    )
    enhanced_query, mode_decision = result
    assert enhanced_query.enhanced_query
    assert mode_decision.mode in ("primary_agent", "worker", "uncertain")
    assert 0.0 <= mode_decision.score <= 1.0
    assert isinstance(mode_decision.reasons, list)


@pytest.mark.integration
async def test_exploration_loop_full_flow(mock_agent, mock_llm, sample_context_query):
    """Given an ExplorationLoop with retrieval tool, When run() is called
    with a ContextEnhancedQuery, Then the loop produces DigestedInformation."""
    loop = ExplorationLoop()
    digested = await loop.run(
        agent=mock_agent,
        messages=[],
        tools=[mock_retrieval_tool()],
        context_enhanced_query=sample_context_query,
        caller="primary_agent",
    )
    assert digested.context_summary
    assert isinstance(digested.key_points, list)


@pytest.mark.integration
async def test_linear_agent_loop_react_flow(mock_agent, mock_llm, mock_tools):
    """Given a LinearAgentLoop with tools, When run() is called with
    structured input, Then the loop executes ReAct iterations and returns output."""
    loop = LinearAgentLoop(max_iterations=5)
    output = await loop.run(
        agent=mock_agent,
        messages=[],
        tools=mock_tools,
        input_data={"query": "Analyze the requirements"},
    )
    assert isinstance(output, str)
    assert len(output) > 0


@pytest.mark.integration
async def test_hybrid_review_deterministic_short_circuit(mock_agent, mock_llm, mock_task, mock_failed_task_result):
    """Given a HybridReviewLoop with deterministic checks, When run() is called
    with a TaskResult that fails deterministic checks, Then short-circuit occurs
    without LLM call, producing a retry/escalate decision."""
    def failing_check(task, task_result):
        return CheckResult(
            check_name="schema_validity",
            passed=False,
            reason="Missing required field",
            decision_override=ReviewStatus.RETRY,
        )

    loop = HybridReviewLoop(deterministic_checks=[failing_check])
    decision = await loop.run(
        agent=mock_agent,
        messages=[],
        tools=[],
        task=mock_task,
        task_result=mock_failed_task_result,
    )
    assert decision.status in ("retry", "escalate_user")
    assert decision.reason


@pytest.mark.integration
async def test_create_loop_factory():
    """Given a LoopType enum value, When create_loop() is called,
    Then the correct loop subclass is instantiated."""
    loop = create_loop(LoopType.CLASSIFICATION)
    assert isinstance(loop, ClassificationLoop)

    loop = create_loop(LoopType.EXPLORATION)
    assert isinstance(loop, ExplorationLoop)

    loop = create_loop(LoopType.LINEAR_AGENT)
    assert isinstance(loop, LinearAgentLoop)

    loop = create_loop(LoopType.HYBRID_REVIEW)
    assert isinstance(loop, HybridReviewLoop)

    with pytest.raises(ValueError, match="Unknown loop type"):
        create_loop("invalid_type")  # type: ignore


@pytest.mark.integration
async def test_all_loops_support_streaming(mock_agent, mock_llm):
    """All four loop types support stream=True, yielding SSE events."""
    for loop_cls, kwargs in [
        (ClassificationLoop, {"user_query": "hello", "session_context": "", "chat_history": []}),
        (ExplorationLoop, {"context_enhanced_query": "test", "caller": "primary_agent"}),
        (LinearAgentLoop, {"input_data": "test"}),
        (HybridReviewLoop, {"task": {}, "task_result": {}, "execution_log": None}),
    ]:
        loop = loop_cls()
        stream = loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            stream=True,
            **kwargs,
        )
        events = [event async for event in stream]
        assert len(events) > 0
```

### Key Test Scenarios

- [x] **Scenario 1**: ClassificationLoop produces valid `ModeDecision` + `ContextEnhancedQuery`
- [x] **Scenario 2**: ExplorationLoop produces valid `DigestedInformation`
- [x] **Scenario 3**: LinearAgentLoop executes ReAct iterations and returns output
- [x] **Scenario 4**: HybridReviewLoop short-circuits on deterministic failure
- [x] **Scenario 5**: `create_loop()` factory instantiates correct subclass for each `LoopType`
- [x] **Scenario 6**: All loops support `stream=True` yielding events

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for each loop module — test error handling, edge cases, fallbacks
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify `tinycua.loops` is importable: `uv run python -c "from tinycua.loops import LoopType, create_loop"`
- [ ] Verify `tinycua` package re-exports loops: `uv run python -c "import tinycua; print(tinycua.loops)"`

### Performance Considerations

- [ ] ClassificationLoop performance: verify LLM call count is exactly 1 per `run()` (fast path)
- [ ] ExplorationLoop: verify `max_search_iterations` prevents runaway iterations

## Proposed Changes

### New Module: `tinycua/loops/`

#### [NEW] `src/tinycua/tinycua/loops/__init__.py`

- **Description**: Package entry point that re-exports `LoopType`, `create_loop`, all four loop classes, config dataclasses, and `CheckResult`.
- **Dependencies**: All other loop source files.

#### [NEW] `src/tinycua/tinycua/loops/types.py`

- **Description**: Defines `LoopType` enum with four values: `CLASSIFICATION`, `EXPLORATION`, `LINEAR_AGENT`, `HYBRID_REVIEW`. Each maps to a string value matching its lowercase name.
- **Dependencies**: None (stdlib only).

#### [NEW] `src/tinycua/tinycua/loops/factory.py`

- **Description**: Implements `create_loop(loop_type: LoopType, *, max_iterations: int = 5, **kwargs) -> BaseLoop` that maps enum values to subclass constructors. Raises `ValueError` for unknown types.
- **Dependencies**: `types.py`, all loop class modules.

#### [NEW] `src/tinycua/tinycua/loops/base.py`

- **Description**: Shared helpers for TINYCUA loops (optional). May contain base configuration dataclasses or utility functions. Kept minimal; only added if common code emerges across loops.
- **Dependencies**: None initially.

#### [NEW] `src/tinycua/tinycua/loops/classification.py`

- **Description**: Implements `ClassificationLoop(BaseLoop)` — fast, high-level context scan + score-based mode classification. Accepts `user_query`, `session_context`, `chat_history`; produces tuple `(ContextEnhancedQuery, ModeDecision)`. Uses LLM to evaluate complexity and context-dependency dimensions, then determines mode.
- **Dependencies**: `BaseLoop`, `tinycua.state.mode_decision`.

#### [NEW] `src/tinycua/tinycua/loops/exploration.py`

- **Description**: Implements `ExplorationLoop(BaseLoop)` — precision-oriented exploration using an injected retrieval tool. Iteratively identifies information gaps, searches session context, judges relevance, and compiles `DigestedInformation`.
- **Dependencies**: `BaseLoop`, `tinycua.state.digested_information`.

#### [NEW] `src/tinycua/tinycua/loops/linear_agent.py`

- **Description**: Implements `LinearAgentLoop(BaseLoop)` — ReAct execution pattern with single input→output contract. No internal routing branches. Supports configurable tool sets and optional `shallow_task_list` parameter.
- **Dependencies**: `BaseLoop`.

#### [NEW] `src/tinycua/tinycua/loops/hybrid_review.py`

- **Description**: Implements `HybridReviewLoop(BaseLoop)` — hybrid deterministic + LLM review. Executes injected deterministic check callables first; short-circuits on failure with a `ReviewerDecision`. Otherwise performs LLM semantic review. Produces `ReviewerDecision` with one of four statuses.
- **Dependencies**: `BaseLoop`, `tinycua.state.reviewer`.

### Modified Files

#### [MODIFY] `src/tinycua/tinycua/__init__.py`

- **Description**: Add re-export of `tinycua.loops` so it's accessible as `tinycua.loops`.
- **Change**: Add `from tinycua import loops` or `from . import loops` import.
- **Breaking changes**: None.

### New Test Files

#### [NEW] `tests/unit/loops/test_types.py`

- **Description**: Unit tests for `LoopType` enum — values, string mapping, iteration.

#### [NEW] `tests/unit/loops/test_factory.py`

- **Description**: Unit tests for `create_loop()` — correct subclass for each type, error on unknown, kwargs forwarding.

#### [NEW] `tests/unit/loops/test_classification.py`

- **Description**: Unit tests for `ClassificationLoop` — construction with rubric params, `run()` with mock LLM, output shape verification, edge cases (empty context, LLM failure).

#### [NEW] `tests/unit/loops/test_exploration.py`

- **Description**: Unit tests for `ExplorationLoop` — construction with mock retrieval tool, `run()` with mock LLM, output verification, edge cases (no relevant context found).

#### [NEW] `tests/unit/loops/test_linear_agent.py`

- **Description**: Unit tests for `LinearAgentLoop` — construction with mock tools, `run()` with mock LLM, ReAct iteration count, tool calling, max iterations reached.

#### [NEW] `tests/unit/loops/test_hybrid_review.py`

- **Description**: Unit tests for `HybridReviewLoop` — construction with mock deterministic checks, short-circuit on failure, all four decision statuses, LLM failure handling.

#### [NEW] `tests/integration/test_custom_loops.py`

- **Description**: Integration tests (defined above in Success Criteria) that exercise full flow with real LLM or SDK mock.

### Test Infrastructure

#### [NEW] `tests/unit/loops/conftest.py`

- **Description**: Shared fixtures for loop tests — `mock_agent`, `mock_llm`, sample state objects, `mock_retrieval_tool`, etc.

#### [MODIFY] `tests/conftest.py` or `tests/integration/conftest.py`

- **Description**: Add shared fixtures for integration tests if not already present.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/loops/` | New | Entire new module — 7 source files (package init, types, factory, base, classification, exploration, linear_agent, hybrid_review) |
| `tinycua/__init__.py` | Modify | Re-export `tinycua.loops` |
| `tinycua/state/` | Unchanged | Consumed by loops but not modified |
| `tinycua-sdk/agent/loop.py` | Unchanged | `BaseLoop` remains untouched |
| `tinycua-sdk/agent/agent.py` | Unchanged | Already supports `loop=` parameter |

## Data Model Changes

```python
# New types in tinycua.loops.types
class LoopType(Enum):
    CLASSIFICATION = "classification"
    EXPLORATION = "exploration"
    LINEAR_AGENT = "linear_agent"
    HYBRID_REVIEW = "hybrid_review"

# New configuration dataclasses in respective loop modules
@dataclass
class ClassificationConfig:
    rubric_dimensions: list[str] = field(default_factory=lambda: ["complexity", "context_dependency"])
    confidence_threshold: float = 0.7
    max_context_tokens: int = 4000

@dataclass
class ExplorationConfig:
    max_search_iterations: int = 3
    relevance_threshold: float = 0.6
    max_results_per_query: int = 5

@dataclass
class LinearAgentConfig:
    system_prompt_template: str = ""
    max_iterations: int = 5
    enable_streaming: bool = True

@dataclass
class HybridReviewConfig:
    deterministic_checks: list[Callable] = field(default_factory=list)
    consecutive_failure_threshold: int = 3
    llm_review_required: bool = True

@dataclass
class CheckResult:
    check_name: str
    passed: bool
    reason: str
    decision_override: ReviewStatus | None = None
```

## API Changes

### New Public API: `tinycua.loops` package

```python
from tinycua.loops import (
    LoopType,
    create_loop,
    ClassificationLoop,
    ExplorationLoop,
    LinearAgentLoop,
    HybridReviewLoop,
    ClassificationConfig,
    ExplorationConfig,
    LinearAgentConfig,
    HybridReviewConfig,
    CheckResult,
)
```

### New Factory Function

```python
def create_loop(
    loop_type: LoopType,
    *,
    max_iterations: int = 5,
    **kwargs,
) -> BaseLoop:
    """Create the appropriate loop instance for the given loop type."""
```

## Dependencies

### External Dependencies

None — all use stdlib (`enum`, `dataclasses`, `typing`) and existing project deps.

### Internal Dependencies

- [x] Requires M1 State Objects (`tinycua.state`) — already implemented
- [x] Depends on SDK `BaseLoop` (`tinycua-sdk`) — already implemented
- [ ] Blocks downstream agent implementations that require a concrete loop type

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| HybridReviewLoop deterministic checks miss edge cases | Medium | Start with simple checks (schema validity, missing fields); extend incrementally |
| ExplorationLoop search loop diverges | High | Hard limit `max_search_iterations` (default 3); stop on no new relevant context |
| ClassificationLoop rubric dimensions change | Low | Rubric dimensions are configurable via constructor |
| SDK `BaseLoop` public API changes | High | Target current `BaseLoop` API; pin SDK version if needed |
| State object interfaces change after loops are built | Medium | Loops produce raw dicts/strings; caller deserializes into state objects — decoupled |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-31*
