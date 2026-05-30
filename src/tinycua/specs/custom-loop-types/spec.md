# Feature Specification: Custom Loop Types (M2)

**Status**: Draft
**Created**: 2026-05-31
**Last Updated**: 2026-05-31
**Subproject(s) Affected**: tinycua, tinycua-sdk

---

## Problem Statement _(mandatory)_

- **Goals**: Provide four canonical custom loop types — Classification, Exploration, Linear Agent, and Hybrid Review — that implement the TINYCUA agent execution patterns defined in the architecture docs. These loops bridge M1 State Objects (typed data) with the SDK's `BaseLoop` (execution foundation) to give each TINYCUA agent a dedicated, testable loop implementation.
- **Gaps**: The architecture docs define eight agents with distinct loop characteristics (see `src/tinycua/docs/architecture/overview.md` — Agent Loop Types table), but no concrete loop implementations exist. The SDK provides `BaseLoop` with public helpers (`build_system_message()`, `process_tool_calls()`, etc.), and M1 provides typed state objects (`ModeDecision`, `DigestedInformation`, `TaskResult`, `ReviewerDecision`, etc.), but there is no code that:
  1. Defines a `LoopType` enum or registry to identify each loop pattern.
  2. Implements the four loop types as `BaseLoop` subclasses with TINYCUA-specific behavior.
  3. Wires M1 state objects as loop inputs/outputs (e.g., Classification loop produces `ModeDecision` + `ContextEnhancedQuery`; Hybrid Review loop consumes `TaskResult` and produces `ReviewerDecision`).
  4. Provides a factory or configuration mechanism to select the correct loop for each TINYCUA agent.
  5. Integrates agent-specific system prompts and tool sets with the loop type.
- **Non-Goals**:
  - This spec does NOT cover the top-level orchestrator (agent-to-agent calling, session lifecycle, Worker orchestration). Those are separate milestones.
  - This spec does NOT cover the full system prompt design for each agent. Prompts are specified at a high level; detailed prompt engineering is deferred to agent implementation milestones.
  - This spec does NOT cover agent factory or runtime wiring beyond loop selection. The `Agent` class in the SDK already accepts a `loop=` parameter.
  - This spec does NOT cover human-in-the-loop continuation, sub-session management, or execution logging at the orchestration level.
  - This spec does NOT modify the SDK's `BaseLoop` or its public helper API.
- **Constraints**:
  - Each loop type MUST be a subclass of `tinycua_sdk.agent.loop.BaseLoop`.
  - Each loop type MUST use only the public helper API of `BaseLoop` (no private `_` methods except the supported `agent._call_llm()` extension point).
  - Each loop type MUST produce/consume M1 state objects where the architecture doc specifies a state object as input or output.
  - Loops MUST support both sync (`run()` returning content) and stream (`run()` returning async generator) execution paths.
  - Loop implementations MUST target Python 3.11+.
  - All existing SDK tests MUST continue to pass.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer building the TINYCUA application creates an agent with the appropriate loop type, runs it with a query, and receives correctly typed output. For example:

- A Query Analyst agent using the **Classification loop** receives a user query + session context and produces a `ModeDecision` + `ContextEnhancedQuery`.
- An Information Digester agent using the **Exploration loop** receives a `ContextEnhancedQuery` and produces `DigestedInformation` by searching session context.
- A Task Analyzer agent using the **Linear Agent loop** receives `DigestedInformation` and produces a `Task` tree.
- A Result Reviewer agent using the **Hybrid Review loop** receives a `TaskResult` + task + execution log and produces a `ReviewerDecision`.

### Acceptance Scenarios

1. **Given** a `ClassificationLoop` configured with classification rubric parameters, **When** `run()` is called with a user query and session context, **Then** the loop produces a `ModeDecision` (with valid mode, score, confidence, reasons) and a `ContextEnhancedQuery` string.

2. **Given** an `ExplorationLoop` with an `EnhancedContextRetrieval` tool, **When** `run()` is called with a `ContextEnhancedQuery`, **Then** the loop produces `DigestedInformation` with `context_summary`, `key_points`, and optional advisory fields.

3. **Given** a `LinearAgentLoop` with tools, **When** `run()` is called with structured input (e.g., `DigestedInformation`), **Then** the loop executes a ReAct-style think→act→observe iteration and produces a single output (e.g., a task list).

4. **Given** a `HybridReviewLoop` with deterministic check functions, **When** `run()` is called with a `TaskResult` and task, **Then** the loop executes deterministic checks first, then LLM semantic review, and produces a `ReviewerDecision` with one of the four statuses (accepted, retry, replan, escalate_user).

5. **Given** a `LoopType` enum, **When** a factory function receives the enum value plus agent configuration, **Then** the correct loop subclass is instantiated with the appropriate parameters.

### Edge Cases

- What happens when the Classification loop receives an empty session context? It should still produce a `ModeDecision` based on the query alone, defaulting to `primary_agent` mode.
- What happens when the Exploration loop finds no relevant context? It should return `DigestedInformation` with empty `key_points` and a `context_summary` indicating no relevant context found.
- What happens when the Linear Agent loop reaches `max_iterations` without producing output? It should return a fallback result indicating the limit was reached (consistent with `BaseLoop` behavior).
- What happens when the Hybrid Review loop receives a `TaskResult` with `status=failed`? The deterministic checks should detect the failure status and produce a retry/replan/escalate decision without calling the LLM.
- What happens when the Hybrid Review loop's LLM call fails mid-review? The loop should return an `escalate_user` decision with the failure reason.
- What happens when all deterministic checks pass but the LLM contradicts them? The LLM verdict should take precedence for semantic decisions, while deterministic failures should be non-overridable (e.g., schema validation failure → immediate retry).

---

## Requirements _(mandatory)_

### Functional Requirements

**Loop type identification:**

- **FR-001**: System MUST provide a `LoopType` enum with values: `CLASSIFICATION`, `EXPLORATION`, `LINEAR_AGENT`, `HYBRID_REVIEW`.
- **FR-002**: Each `LoopType` value MUST map to a corresponding `BaseLoop` subclass.

**Classification loop (Query Analyst):**

- **FR-003**: `ClassificationLoop` MUST accept a `user_query`, `session.chat_history`, and `session.context` as inputs.
- **FR-004**: `ClassificationLoop` MUST produce a `ContextEnhancedQuery` (the query enriched with high-level session context) and a `ModeDecision` (with `mode`, `score`, `confidence`, `reasons`, and optional `uncertain_next_action`).
- **FR-005**: `ClassificationLoop` MUST implement score-based classification using [NEEDS CLARIFICATION: scoring rubric dimensions — see `task-classification.md`]. The loop MUST evaluate at least complexity and context-dependency dimensions.
- **FR-006**: `ClassificationLoop` MUST NOT perform deep retrieval — it scans session context directly as a fast, high-level pass.

**Exploration loop (Information Digester):**

- **FR-007**: `ExplorationLoop` MUST accept a `context_enhanced_query` and caller identifier (`primary_agent` or `worker`).
- **FR-008**: `ExplorationLoop` MUST use an `EnhancedContextRetrieval` tool to search session context for information gaps identified in the query.
- **FR-009**: `ExplorationLoop` MUST produce `DigestedInformation` with `context_summary`, `key_points`, and optional `advisory_instructions`, `constraints`, and `known_gaps`.
- **FR-010**: `ExplorationLoop` MUST iterate: identify information gaps → search session context → judge relevance → compile findings. The loop stops when no new relevant context is found or max_iterations is reached.

**Linear Agent loop (Task Analyzer, Task Executor, Task Assessor, Primary Agent):**

- **FR-011**: `LinearAgentLoop` MUST accept structured input (e.g., `DigestedInformation`, focused task context) and produce a single structured output (e.g., task list, `TaskResult`, `ReviewerDecision`, or response).
- **FR-012**: `LinearAgentLoop` MUST implement a ReAct execution pattern (think → act → observe → repeat) with no internal routing branches. It has a single input→output contract.
- **FR-013**: `LinearAgentLoop` MUST support configurable tool sets per agent role (e.g., Task Executor gets different tools than Task Assessor).
- **FR-014**: `LinearAgentLoop` MUST support an optional `shallow_task_list` parameter for scope awareness without exposing full task details.

**Hybrid Review loop (Result Reviewer):**

- **FR-015**: `HybridReviewLoop` MUST accept a `TaskResult`, the corresponding `Task`, and an `execution_log`.
- **FR-016**: `HybridReviewLoop` MUST execute deterministic checks (schema validity, missing fields, evidence consistency) BEFORE calling the LLM for semantic review.
- **FR-017**: `HybridReviewLoop` MUST produce a `ReviewerDecision` with `task_id`, `status` (accepted, retry, replan, escalate_user), `reason`, `confidence`, and optional `context_updates` and `retry_instructions`.
- **FR-018**: Deterministic check failures MUST short-circuit to an immediate `retry` or `escalate_user` decision without LLM invocation.
- **FR-019**: `HybridReviewLoop` MUST support configurable deterministic check functions injected at construction time.

**Factory and configuration:**

- **FR-020**: System MUST provide a function `create_loop(loop_type: LoopType, **kwargs) -> BaseLoop` that instantiates the correct loop subclass with the provided keyword arguments.
- **FR-021**: System MUST support passing agent-specific system prompt templates to each loop type via `instructions` parameter.
- **FR-022**: All four loop types MUST support both sync `run()` and streaming `run(stream=True)` execution paths, delegating to `BaseLoop`'s public helpers.

### Key Entities

- **LoopType**: Enum identifying the four loop patterns (CLASSIFICATION, EXPLORATION, LINEAR_AGENT, HYBRID_REVIEW).
- **ClassificationLoop**: `BaseLoop` subclass for Query Analyst. Produces `ModeDecision` + `ContextEnhancedQuery`.
- **ExplorationLoop**: `BaseLoop` subclass for Information Digester. Produces `DigestedInformation` via search-based exploration.
- **LinearAgentLoop**: `BaseLoop` subclass for agents with a single input→output ReAct contract (Task Analyzer, Task Executor, Task Assessor, Primary Agent).
- **HybridReviewLoop**: `BaseLoop` subclass for Result Reviewer. Produces `ReviewerDecision` via deterministic checks + LLM semantic review.
- **LoopFactory**: Function that maps `LoopType` enum values to concrete `BaseLoop` subclass instances with the correct configuration.

---

## Success Criteria _(mandatory)_

- [ ] **`LoopType` enum defined**: Four values in `tinycua.loops` module, importable from a single entry point.
- [ ] **`ClassificationLoop` implemented**: Produces valid `ModeDecision` + `ContextEnhancedQuery` for test queries with known session context.
- [ ] **`ExplorationLoop` implemented**: Produces valid `DigestedInformation` with at least `context_summary` and `key_points`.
- [ ] **`LinearAgentLoop` implemented**: Executes ReAct loop with configurable tools, returns structured output.
- [ ] **`HybridReviewLoop` implemented**: Executes deterministic checks before LLM review, short-circuits on deterministic failure, produces `ReviewerDecision` with valid status.
- [ ] **`create_loop()` factory function**: Maps each `LoopType` value to the correct subclass with kwargs forwarded.
- [ ] **All loop types support sync + stream**: Each loop implements both `run()` paths delegating to `BaseLoop` public helpers.
- [ ] **Unit test coverage > 85%**: All four loop types, factory function, deterministic check logic covered.
- [ ] **All existing SDK and M1 tests pass**: No regressions in `tinycua-sdk` or `tinycua.state`.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `LoopType` enum values and string mapping.
- `create_loop()` factory: correct subclass instantiation for each loop type, error on unknown type.
- `ClassificationLoop`: construction with rubric parameters, `run()` with mock LLM, verification of `ModeDecision` output shape.
- `ExplorationLoop`: construction with mock retrieval tool, `run()` with mock LLM, verification of `DigestedInformation` output.
- `LinearAgentLoop`: construction with mock tools, `run()` with mock LLM, verification of ReAct iteration and output shape.
- `HybridReviewLoop`: construction with mock deterministic checks, `run()` with mock LLM, short-circuit on deterministic failure, verification of `ReviewerDecision` output for each status.
- Edge cases: empty inputs, max_iterations reached, tool call failures, LLM failures.

### Integration Tests

- `ClassificationLoop` with real LLM (or SDK's standard integration mock): full flow from query + context → `ModeDecision`.
- `ExplorationLoop` with real LLM + mock retrieval tool: full exploration flow → `DigestedInformation`.
- `LinearAgentLoop` with real LLM + real tools: tool calling within ReAct loop.
- `HybridReviewLoop` with real LLM + deterministic checks: full review flow → `ReviewerDecision`.

### Manual Tests _(if applicable)_

- Visual inspection of `ModeDecision` confidence/score distributions across varied queries.
- Verification that `HybridReviewLoop` deterministic checks catch known-bad task results before LLM review.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| `LoopType` enum | TODO | |
| `ClassificationLoop` | TODO | |
| `ExplorationLoop` | TODO | |
| `LinearAgentLoop` | TODO | |
| `HybridReviewLoop` | TODO | |
| `create_loop()` factory | TODO | |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **Should `ContextEnhancedQuery` be a separate type or inline in the loop's output?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-07
   - **Status**: Discussion
   - **Proposed Answer**: The loop should accept `user_query: str` and `session_context: str` and return a tuple `(ContextEnhancedQuery, ModeDecision)`. The `ContextEnhancedQuery` is a dedicated M1 state object for type safety.

2. **How should the Exploration loop signal "no relevant context found"?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-07
   - **Status**: Discussion
   - **Proposed Answer**: Return `DigestedInformation` with empty `key_points` list, `context_summary="No relevant context found in session"`, and `known_gaps=[...]` listing what was searched for. The caller (Primary Agent or Worker) decides how to proceed.

3. **Should `HybridReviewLoop` deterministic checks be a protocol/ABC or simple callable list?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-07
   - **Status**: Discussion
   - **Proposed Answer**: A list of callables `list[Callable[[Task, TaskResult], CheckResult | None]]` where `CheckResult` has `passed: bool` and `decision_override: ReviewStatus | None`. If any check returns `passed=False` with a non-None `decision_override`, the loop short-circuits to that decision.

4. **Which agents share the `LinearAgentLoop` vs needing their own unique loop?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-07
   - **Status**: Discussion
   - **Proposed Answer**: Task Analyzer, Task Executor, Task Assessor, and Primary Agent all use `LinearAgentLoop` configured with different tools and prompts. Each is instantiated via the factory with appropriate parameters. If an agent's loop pattern diverges significantly in a future milestone, a new loop type can be added.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
