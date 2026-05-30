# Design Document: Custom Loop Types (M2)

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-05-31

---

## Overview

Implement four canonical custom loop types — Classification, Exploration, Linear Agent, and Hybrid Review — as `BaseLoop` subclasses in a new `tinycua.loops` module. Each loop type implements the execution pattern defined in the architecture docs for its corresponding TINYCUA agent(s), bridging M1 State Objects (typed data) with the SDK's `BaseLoop` (execution foundation). A `LoopType` enum and `create_loop()` factory provide discovery and instantiation.

The primary subproject affected is **tinycua** (new `tinycua/loops/` module). The **tinycua-sdk** subproject is a dependency but is not modified.

---

## Architecture

### Module Layout

```
src/tinycua/tinycua/
├── __init__.py
├── agent/                          # existing
├── cli/                            # existing
├── state/                          # existing (M1)
└── loops/                          # NEW
    ├── __init__.py                 # Re-exports LoopType, create_loop, all loop classes
    ├── types.py                    # LoopType enum
    ├── factory.py                  # create_loop() factory function
    ├── base.py                     # Shared helpers for TINYCUA loops (optional)
    ├── classification.py           # ClassificationLoop (Query Analyst)
    ├── exploration.py              # ExplorationLoop (Information Digester)
    ├── linear_agent.py             # LinearAgentLoop (Task Analyzer, Task Executor, Task Assessor, Primary Agent)
    └── hybrid_review.py            # HybridReviewLoop (Result Reviewer)
```

### High-Level Architecture

```
                    ┌─────────────────────────────────┐
                    │         tinycua.loops            │
                    │  (Custom Loop Types - M2)        │
                    │                                  │
                    │  LoopType enum                   │
                    │  create_loop() factory           │
                    │                                  │
                    │  ┌──────────┐ ┌──────────────┐   │
                    │  │Classifica│ │ Exploration   │   │
                    │  │tionLoop  │ │ Loop          │   │
                    │  └────┬─────┘ └──────┬────────┘   │
                    │       │              │            │
                    │  ┌────┴─────┐ ┌──────┴────────┐   │
                    │  │Linear    │ │ HybridReview   │   │
                    │  │AgentLoop │ │ Loop           │   │
                    │  └──────────┘ └───────────────┘   │
                    │         │                          │
                    └─────────┼──────────────────────────┘
                              │ extends
                    ┌─────────┴──────────────────────────┐
                    │     tinycua_sdk.agent.loop         │
                    │         BaseLoop                   │
                    │  (public helpers:                  │
                    │   build_system_message,            │
                    │   process_tool_calls,              │
                    │   process_stream_iteration,        │
                    │   process_stream_tool_calls,       │
                    │   last_assistant_content)          │
                    └────────────────────────────────────┘
                              │ produces/consumes
                    ┌─────────┴──────────────────────────┐
                    │     tinycua.state (M1)              │
                    │  ModeDecision, DigestedInformation, │
                    │  Task, TaskResult, ReviewerDecision │
                    │  AgentState, ExecutionLog, etc.     │
                    └────────────────────────────────────┘
```

### Agent-to-Loop Mapping

| Agent | Loop Type | Input State Objects | Output State Objects |
|-------|-----------|--------------------|---------------------|
| Query Analyst | ClassificationLoop | `user_query` (str), `session.chat_history` (list[dict]), `session.context` (str) | `ContextEnhancedQuery`, `ModeDecision` |
| Information Digester | ExplorationLoop | `context_enhanced_query` (str), caller (str) | `DigestedInformation` |
| Task Creation* | Process (uses LinearAgentLoop) | `DigestedInformation` | `Task` tree |
| Task Assessor | LinearAgentLoop | task context (str) | selection verdict |
| Task Analyzer | LinearAgentLoop | `DigestedInformation` or task context | `Task` list |
| Task Executor | LinearAgentLoop | focused task context, shallow task list | `TaskResult` |
| Result Reviewer | HybridReviewLoop | `Task`, `TaskResult`, `ExecutionLog` | `ReviewerDecision` |
| Primary Agent | LinearAgentLoop | CEQ + DI + WorkerResult | final Response |

*\*Task Creation is a Process Spec (not an agent) that combines Task Assessor + Task Analyzer invocations. Its orchestration is handled by the Worker, not by a single loop instance.*

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/loops/` | New | Entire new module — 7 source files |
| `tinycua/__init__.py` | Modified | May re-export `tinycua.loops` |
| `tinycua/state/` | Unchanged | Consumed by loops but not modified |
| `tinycua-sdk/agent/loop.py` | Unchanged | BaseLoop remains untouched |
| `tinycua-sdk/agent/agent.py` | Unchanged | Already supports `loop=` parameter |

---

## Data Model

### LoopType Enum

```python
from enum import Enum

class LoopType(Enum):
    """Canonical TINYCUA custom loop types."""
    CLASSIFICATION = "classification"     # Query Analyst
    EXPLORATION = "exploration"           # Information Digester
    LINEAR_AGENT = "linear_agent"         # Task Analyzer, Task Executor, Task Assessor, Primary Agent
    HYBRID_REVIEW = "hybrid_review"       # Result Reviewer
```

### Loop-Specific Configuration

Each loop subclass accepts configuration parameters beyond the standard `max_iterations`:

```python
@dataclass
class ClassificationConfig:
    """Configuration for ClassificationLoop."""
    rubric_dimensions: list[str] = field(default_factory=lambda: ["complexity", "context_dependency"])
    confidence_threshold: float = 0.7
    max_context_tokens: int = 4000

@dataclass
class ExplorationConfig:
    """Configuration for ExplorationLoop."""
    max_search_iterations: int = 3
    relevance_threshold: float = 0.6
    max_results_per_query: int = 5

@dataclass
class LinearAgentConfig:
    """Configuration for LinearAgentLoop."""
    system_prompt_template: str = ""  # Agent-specific prompt
    max_iterations: int = 5
    enable_streaming: bool = True

@dataclass
class HybridReviewConfig:
    """Configuration for HybridReviewLoop."""
    deterministic_checks: list[Callable] = field(default_factory=list)
    consecutive_failure_threshold: int = 3
    llm_review_required: bool = True
```

### CheckResult (for HybridReview deterministic checks)

```python
@dataclass
class CheckResult:
    """Result of a single deterministic check in HybridReviewLoop."""
    check_name: str
    passed: bool
    reason: str
    decision_override: ReviewStatus | None = None
    # If decision_override is set and passed is False, the loop short-circuits
    # to that decision without calling the LLM.
```

---

## API / Interface Contracts

### Public API: `tinycua.loops` package

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

### Loop Signatures

```python
class ClassificationLoop(BaseLoop):
    """Fast, high-level context scan + score-based mode classification.

    Produces ContextEnhancedQuery + ModeDecision from user query + session context.
    """

    def __init__(
        self,
        max_iterations: int = 5,
        rubric_dimensions: list[str] | None = None,
        confidence_threshold: float = 0.7,
    ) -> None: ...

    async def run(
        self,
        agent: Agent,
        messages: list[dict[str, Any]],
        tools: list[Tool],
        stream: bool = False,
        *,
        user_query: str,
        session_context: str,
        chat_history: list[dict],
    ) -> tuple[str, ModeDecision] | AsyncIterator[dict]:
        """
        Run the classification loop.

        Returns (context_enhanced_query_text, mode_decision) for sync,
        or yields SSE events for stream.
        """


class ExplorationLoop(BaseLoop):
    """Precision-oriented exploration using Enhanced Context Retrieval.

    Iteratively identifies information gaps, searches session context,
    judges relevance, and compiles DigestedInformation.
    """

    def __init__(
        self,
        max_iterations: int = 5,
        max_search_iterations: int = 3,
        relevance_threshold: float = 0.6,
    ) -> None: ...

    async def run(
        self,
        agent: Agent,
        messages: list[dict[str, Any]],
        tools: list[Tool],
        stream: bool = False,
        *,
        context_enhanced_query: str,
        caller: str = "primary_agent",  # "primary_agent" | "worker"
    ) -> DigestedInformation | AsyncIterator[dict]:
        """
        Run the exploration loop.

        Returns DigestedInformation for sync, or yields SSE events for stream.
        """


class LinearAgentLoop(BaseLoop):
    """ReAct loop with single input→output contract, no internal routing branches.

    Used by Task Analyzer, Task Executor, Task Assessor, and Primary Agent
    with different tool sets and system prompts.
    """

    def __init__(
        self,
        max_iterations: int = 5,
        system_prompt_template: str = "",
        shallow_task_list: list[dict] | None = None,
    ) -> None: ...

    async def run(
        self,
        agent: Agent,
        messages: list[dict[str, Any]],
        tools: list[Tool],
        stream: bool = False,
        *,
        input_data: str | dict,
    ) -> str | AsyncIterator[dict]:
        """
        Run the linear agent loop.

        Returns output content str for sync, or yields SSE events for stream.
        The caller deserializes the output into the expected state object.
        """


class HybridReviewLoop(BaseLoop):
    """Hybrid deterministic + LLM review loop for Result Reviewer.

    Executes deterministic checks first; short-circuits on failure.
    Otherwise performs LLM semantic review and produces ReviewerDecision.
    """

    def __init__(
        self,
        max_iterations: int = 3,
        deterministic_checks: list[Callable] | None = None,
        consecutive_failure_threshold: int = 3,
    ) -> None: ...

    async def run(
        self,
        agent: Agent,
        messages: list[dict[str, Any]],
        tools: list[Tool],
        stream: bool = False,
        *,
        task: dict,          # Task state object as dict
        task_result: dict,   # TaskResult state object as dict
        execution_log: dict | None = None,
    ) -> ReviewerDecision | AsyncIterator[dict]:
        """
        Run the hybrid review loop.

        Returns ReviewerDecision for sync, or yields SSE events for stream.
        """
```

### Factory Function

```python
def create_loop(
    loop_type: LoopType,
    *,
    max_iterations: int = 5,
    **kwargs,
) -> BaseLoop:
    """Create the appropriate loop instance for the given loop type.

    Args:
        loop_type: The type of loop to create.
        max_iterations: Maximum iterations for the loop.
        **kwargs: Additional keyword arguments forwarded to the loop constructor.

    Returns:
        An instance of the corresponding BaseLoop subclass.

    Raises:
        ValueError: If loop_type is unknown.
    """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Unknown `LoopType` value | `ValueError("Unknown loop type: ...")` | Raised by `create_loop()` |
| Deterministic check failure in `HybridReviewLoop` | Short-circuit to `retry` or `escalate_user` | No exception raised; loop returns `ReviewerDecision` with appropriate status |
| LLM failure during any loop | `asyncio.CancelledError` (cancellation) or provider exception | Consistent with `BaseLoop` behavior |
| Max iterations reached in `ClassificationLoop` | Return fallback `ModeDecision` with `mode="primary_agent"` and low confidence | Graceful degradation |
| Empty `DigestedInformation` from `ExplorationLoop` | Return with empty `key_points` and appropriate `context_summary` | Not an error; caller handles insufficient context |

---

## Implementation Phases

### Phase 1 — Foundation

- [ ] Create `tinycua/loops/` package with `__init__.py`
- [ ] Implement `LoopType` enum in `types.py`
- [ ] Implement `create_loop()` factory in `factory.py`
- [ ] Write unit tests for enum values, factory mapping, error cases
- [ ] Write integration test skeleton for factory

### Phase 2 — ClassificationLoop

- [ ] Implement `ClassificationLoop` in `classification.py` extending `BaseLoop`
- [ ] Implement score-based classification rubric (complexity + context-dependency)
- [ ] Integrate `ModeDecision` and `ContextEnhancedQuery` output
- [ ] Write unit tests: mock LLM, verify output shape, edge cases (empty context)
- [ ] Write integration test: real LLM call with known query/context

### Phase 3 — ExplorationLoop

- [ ] Implement `ExplorationLoop` in `exploration.py` extending `BaseLoop`
- [ ] Implement gap identification → search → relevance judging → compilation loop
- [ ] Integrate with `EnhancedContextRetrieval` tool mock
- [ ] Write unit tests: mock retrieval tool, verify `DigestedInformation` output
- [ ] Write integration test: real LLM + mock retrieval tool

### Phase 4 — LinearAgentLoop

- [ ] Implement `LinearAgentLoop` in `linear_agent.py` extending `BaseLoop`
- [ ] Implement ReAct pattern with configurable tool sets
- [ ] Support `shallow_task_list` parameter for scope awareness
- [ ] Write unit tests: mock tools, verify ReAct iteration, tool calling
- [ ] Write integration test: real LLM + real tools

### Phase 5 — HybridReviewLoop

- [ ] Implement `HybridReviewLoop` in `hybrid_review.py` extending `BaseLoop`
- [ ] Implement deterministic check infrastructure (`CheckResult`, check list execution)
- [ ] Implement LLM semantic review with fallback on deterministic failure
- [ ] Integrate `ReviewerDecision` output with context updates and retry instructions
- [ ] Write unit tests: short-circuit on deterministic failure, all four decision statuses
- [ ] Write integration test: real LLM + deterministic checks

### Phase 6 — Final verification

- [ ] All unit tests pass with > 85% coverage
- [ ] All integration tests pass
- [ ] All existing SDK tests pass (no regressions)
- [ ] All existing M1 state tests pass
- [ ] `tinycua.loops` is importable from `tinycua` package

---

## Technical Decisions

1. **Decision**: Four loop types rather than one per agent.
   - **Reason**: Many agents share the same loop pattern (Linear Agent loop serves 4 agents; Hybrid Review loop serves 1). Four types maps cleanly to the four fundamental execution patterns in the architecture.
   - **Alternatives Considered**: One loop per agent (8 types) — introduces unnecessary duplication since 4 agents share the same ReAct loop pattern.

2. **Decision**: Loop configuration via constructor kwargs rather than a monolithic config object.
   - **Reason**: Each loop type has different configuration needs. Constructor kwargs are simple, type-checkable, and consistent with `BaseLoop.__init__(max_iterations=...)`.
   - **Alternatives Considered**: Single `LoopConfig` union type — adds complexity without benefit since loops are instantiated individually.

3. **Decision**: HybridReviewLoop uses a list of callables for deterministic checks rather than a dedicated check protocol/ABC.
   - **Reason**: Maximum flexibility — callables can be functions, lambdas, or bound methods. The simple `CheckResult` return type provides enough structure for short-circuit decisions.
   - **Alternatives Considered**: ABC with `Check` interface — more ceremony for the same capability. Listed as an Open Question in the spec for further discussion.

4. **Decision**: Loop `run()` methods accept state object data as dicts (not typed state objects).
   - **Reason**: `BaseLoop.run()` works with `list[dict]` messages and `dict` tool responses. Accepting typed state objects would require conversion at the boundary. Dicts keep the interface consistent with `BaseLoop` and downstream consumers can deserialize to typed objects.
   - **Alternatives Considered**: Typed state objects as inputs — adds type safety but breaks the `BaseLoop.run()` interface convention. This can evolve to typed wrappers in a future milestone.

5. **Decision**: `create_loop()` returns `BaseLoop` (not a union type).
   - **Reason**: All custom loop types extend `BaseLoop`, and the factory is only used for initial construction. Callers that need specific loop type methods can cast or access through the type enum.
   - **Alternatives Considered**: Union return type `ClassificationLoop | ExplorationLoop | ...` — verbose, requires updating when new loop types are added.

6. **Decision**: The `tinycua.loops` module does NOT depend on `tinycua.state` for internal validation.
   - **Reason**: State object validation is already handled by M1's `__post_init__`. The loop produces raw data that the caller serializes into state objects. This avoids redundant validation and keeps loop code focused on execution logic.
   - **Alternatives Considered**: Loops import and construct state objects directly — creates circular dependencies if loops ever need to be reused in contexts where state objects differ.

7. **Decision**: ExplorationLoop uses an abstract "retrieval tool" interface (duck-typed) rather than importing `EnhancedContextRetrieval` directly.
   - **Reason**: Keeps the loop testable without real retrieval infrastructure. Any tool that accepts a search query and returns context can be injected.
   - **Alternatives Considered**: Direct import of `EnhancedContextRetrieval` — creates tight coupling and makes testing harder.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Spec Open Questions unresolved before implementation | Medium | Medium | Mark all with "Discussion" status; implement the proposed answer as default behavior; revisit when question is resolved |
| HybridReviewLoop deterministic checks miss edge cases | Medium | High | Start with simple checks (schema validity, missing fields); extend incrementally based on real review failures |
| ExplorationLoop search loop diverges (infinite iterations) | Low | High | Hard limit `max_search_iterations` (default 3); stop condition when no new relevant context found; guard against identical queries |
| ClassificationLoop rubric dimensions change | Low | Medium | Rubric dimensions are configurable via constructor; defaults match architecture docs |
| SDK `BaseLoop` public API changes | Low | High | M2 targets current `BaseLoop` API; pin SDK version in `pyproject.toml` dependency if needed |
| Performance of LLM-based classification vs deterministic | Low | Low | ClassificationLoop uses LLM for high-level scan (architecture requirement); deterministic optimizations possible later |

---

## References

- Spec: `./spec.md`
- M1 State Objects spec: `../../specs/state-objects/spec.md`
- Architecture overview: `../../docs/architecture/overview.md`
- Query Analyst: `../../docs/architecture/query-analyst.md`
- Information Digestion: `../../docs/architecture/information-digestion.md`
- Task Analysis: `../../docs/architecture/task-analysis.md`
- Task Execution: `../../docs/architecture/task-execution.md`
- Task Creation: `../../docs/architecture/task-creation.md`
- Result Reviewer: `../../docs/architecture/result-reviewer.md`
- Primary Agent: `../../docs/architecture/primary-agent.md`
- SDK BaseLoop: `../../../tinycua-sdk/tinycua_sdk/agent/loop.py`
- SDK Custom Loop API spec: `../../../tinycua-sdk/specs/custom-loop-api/spec.md`
- SDK Custom Loop API design: `../../../tinycua-sdk/specs/custom-loop-api/design.md`
