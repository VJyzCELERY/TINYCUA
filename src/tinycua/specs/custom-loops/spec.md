# Feature Specification: Custom Loop Types (M2)

**Status**: Draft
**Created**: 2026-05-31
**Last Updated**: 2026-05-31
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Provide reusable custom agent loop strategies where the default SDK loop is insufficient — Classification, Exploration, and Hybrid Review — while using `tinycua_sdk.agent.loop.BaseLoop` directly for standard single-input/single-output agents such as Task Analyzer and Task Assessor. Custom loop types are thin adapters on top of `tinycua_sdk` (`BaseLoop`, `Agent`, `LLMClient`, `LanguageModel`, `Tool`) that customize prompt structure, output schemas, and control flow (e.g., iterative retrieval, two-phase review) without reimplementing LLM orchestration, tool execution, or streaming infrastructure.
- **Gaps**: The architecture defines agent loop types conceptually in `src/tinycua/docs/architecture/overview.md` (see the Agent Loop Types table), but there is no implementation of the custom loop strategies needed by specialized agents. Each agent spec (query-analyst.md, information-digestion.md, task-analysis.md, task-assessor.md, task-execution.md, result-reviewer.md, primary-agent.md) describes what the agent does and what it produces, but the loop mechanics — how an agent processes input, decides to continue or stop, uses tools, and produces output — are not consistently mapped to SDK primitives. M1 (State Objects) provides the data types. `tinycua_sdk` provides the standard execution infrastructure (`BaseLoop`, `Agent`, `Tool`). This feature must define only the additional custom strategies needed beyond the SDK default and explicitly map straightforward agents to direct SDK `BaseLoop` usage.
- **Non-Goals**: This spec does NOT cover individual agent implementations (M4), system prompts (M5), agent factory (M3), agent-to-agent calling (M7), session system (M8), worker orchestration (M9), or top-level orchestrator (M10). This spec does NOT define new LLM backend abstractions, tool-calling protocols, or event streaming infrastructure — those are provided by `tinycua_sdk`. The ReAct loop pattern is provided by `tinycua_sdk.agent.loop.BaseLoop`; this spec defines domain-specific strategies on top of it. The Iterative Decomposition Loop (Task Creation) is a process-level orchestration concern, not an agent-internal loop, and is deferred to M9 (Worker Orchestration).
- **Constraints**:
  - Loop types must consume and produce the state objects defined in M1 (`tinycua.state`).
  - Loop types must be Python classes or callables importable by the Agent Factory (M3).
  - Loop types MUST use `tinycua_sdk` for LLM orchestration and tool integration. Specifically: extend or compose with `tinycua_sdk.agent.loop.BaseLoop`; use `tinycua_sdk.agent.Agent` for LLM interaction; use `tinycua_sdk.agent.llm_client.LLMClient` for provider communication; use `tinycua_sdk.agent.llm_model.LanguageModel` for model configuration; use `tinycua_sdk.tools.decorators.Tool` for tool definitions.
  - Loop types MUST NOT define custom LLM backend protocols, tool-calling loops, or streaming infrastructure — the SDK provides these.
  - Each loop type must expose a uniform interface by conforming to `BaseLoop.run()`.
  - Must target Python 3.12+.
  - No orchestration-level concerns (session management, inter-agent routing) inside loops — loops operate within a single agent invocation.

---

## User Scenarios & Testing

### Primary Scenario

A developer implementing the Agent Factory (M3) instantiates each agent with the correct loop type, SDK `Agent` configuration (`LanguageModel`, `Tool` objects, `AgentPolicy`), and the loop processes input through its custom strategy on top of the SDK's execution infrastructure, producing the correct output type as defined in its architecture spec.

### Acceptance Scenarios

1. **Given** a Classification loop configured as the Query Analyst using an SDK `Agent` with a classification system prompt, **When** invoked with a user query and session context, **Then** it produces a `ContextEnhancedQuery` and `ModeDecision` with valid fields (mode, score, confidence, reasons).
2. **Given** an Exploration loop configured as the Information Digester extending SDK's `BaseLoop` with an Enhanced Context Retrieval `Tool`, **When** invoked with a `ContextEnhancedQuery`, **Then** it produces a `DigestedInformation` with at minimum `context_summary` and `key_points`.
3. **Given** Task Analyzer configured with the SDK's default `BaseLoop`, an SDK `Agent`, task analysis prompt, and output schema validation, **When** invoked with `DigestedInformation`, **Then** it produces a `Task` tree (root with child_tasks) where each leaf node has required fields.
4. **Given** Task Assessor configured with the SDK's default `BaseLoop`, an SDK `Agent`, assessment prompt, and output schema validation, **When** invoked with a `Task` tree and `WorkerConfig`, **Then** it returns a selection of task IDs marked for decomposition.
5. **Given** a Hybrid Review loop configured as the Result Reviewer composing SDK's `BaseLoop` for semantic review with pluggable deterministic rules, **When** invoked with a `TaskResult`, **Then** it produces a `ReviewerDecision` with `status` (accepted/retry/replan/escalate_user) and optional `context_updates`.

### Edge Cases

- What happens when the LLM returns malformed output that doesn't match the expected schema? The loop must retry via the SDK's retry infrastructure or fail with a clear error.
- What happens when tool calls fail (e.g., Enhanced Context Retrieval returns empty)? The loop must handle gracefully without crashing.
- What happens when the Exploration loop finds no relevant context? It must produce a `DigestedInformation` that explicitly notes the gap via `known_gaps`.
- What happens with empty input strings? The loop should reject with a validation error before making an LLM call.
- What happens when the Classification loop's scores are all low (high uncertainty)? It must set `mode=uncertain` with a non-null `uncertain_next_action`.
- What happens when the Hybrid Review loop cannot decide (contradictory signals between deterministic and LLM checks)? The deterministic check should take precedence for schema-level validation; the LLM check handles semantic evaluation.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a **Classification Loop** that implements the Query Analyst's flow: high-level context scan → produce `ContextEnhancedQuery` → score-based mode classification → produce `ModeDecision`. The loop must accept `user_query`, `chat_history`, and `session_context` as input. Implemented as a single SDK `Agent.run()` call with a structured system prompt and no tools.
- **FR-002**: The Classification Loop MUST support multi-dimensional scoring with at least three dimensions: task complexity, context dependency, and safety/risk. The loop MUST include anti-laziness safeguards: a rationale for `primary_agent` must explain why Worker decomposition is not needed; a rationale for `worker` must explain the decomposition benefit; `uncertain` mode must set `uncertain_next_action`.
- **FR-003**: System MUST provide an **Exploration Loop** that implements the Information Digester's flow: identify information gaps → invoke Enhanced Context Retrieval → extract relevant context → remove distractions → preserve task-critical details → structure into `DigestedInformation`. The loop must accept a `ContextEnhancedQuery` and have access to an Enhanced Context Retrieval SDK `Tool`.
- **FR-004**: The Exploration Loop MUST support iterative refinement by extending SDK's `BaseLoop`: the agent can identify gaps, retrieve via SDK tool calls, evaluate relevance, and decide to retrieve again or stop. The stop condition is when identified gaps are sufficiently addressed or the retrieval tool returns no new information. The SDK's `BaseLoop` handles the tool-calling iteration; the loop adds gap-evaluation logic.
- **FR-005**: The system MUST use the SDK's default `tinycua_sdk.agent.loop.BaseLoop` directly for agents with a single input→output contract and no custom routing, exploration, or deterministic-review phases. Task Analyzer and Task Assessor belong to this category. No custom `LinearAgentLoop`, `SimpleLoop`, or equivalent wrapper should be introduced unless future requirements need behavior beyond `BaseLoop` plus output validation.
- **FR-006**: Standard `BaseLoop` agents MUST support optional SDK `Tool` objects through the SDK's built-in tool-calling loop. Agents configured with tools use `BaseLoop` internal iteration (think→act→observe→repeat); agents without tools perform pure reasoning via the LLM. Output schema validation may wrap the result, but the execution loop remains SDK `BaseLoop`.
- **FR-007**: System MUST provide a **Hybrid Review Loop** that combines deterministic validation with LLM-based semantic review via SDK's `BaseLoop`. The loop must:
  - First perform deterministic checks (schema validity, missing fields, required structure).
  - Then perform LLM-based semantic review using SDK's `Agent.run()` (correctness against success criteria, sufficiency, context propagation needs).
  - Produce a `ReviewerDecision` with one of four statuses: `accepted`, `retry`, `replan`, `escalate_user`.
  - When `accepted`, compute `context_updates` for unfinished/upcoming tasks.
  - When `retry`, include `retry_instructions` for the next executor attempt.
  - When `replan`, record the rationale for roadmap revision.
  - When `escalate_user`, include a clear explanation for the user.
- **FR-008**: All loop types MUST integrate with `tinycua_sdk` as their execution infrastructure:
  - Extend or compose with `tinycua_sdk.agent.loop.BaseLoop` for the `run()` interface.
  - Use `tinycua_sdk.agent.Agent` for LLM interaction (configured with `LanguageModel`, `Tool` objects, `AgentPolicy`).
  - Use `tinycua_sdk.agent.llm_client.LLMClient` for provider communication — NO custom LLM backend protocols.
  - Use `tinycua_sdk.tools.decorators.Tool` for tool definitions — NO custom tool dataclasses.
  - The input and output types MUST be M1 state objects or plain dicts with documented schemas.
- **FR-009**: All loop types MUST handle LLM invocation errors via the SDK's built-in retry infrastructure. The SDK's `BaseLoop` and `LLMClient` handle transient retries; loop types propagate permanent failures as typed exceptions.
- **FR-010**: All loop types MUST validate their output against the expected schema before returning. If validation fails, the loop should retry via the SDK's infrastructure with the validation error in context, then fail with a clear error if all retries are exhausted.
- **FR-011**: The Hybrid Review Loop MUST distinguish between deterministic validation failures (which should fail closed — escalate) and semantic concerns (which allow retry/replan).

### Key Entities

All entities build on `tinycua_sdk` infrastructure:

- **SDK Integration Point**: All custom loop types extend `tinycua_sdk.agent.loop.BaseLoop` and integrate with `tinycua_sdk.agent.Agent`. The SDK provides: tool-calling execution loop (`BaseLoop`), LLM provider abstraction (`LLMClient`), model configuration (`LanguageModel`), tool infrastructure (`Tool`, `ToolExecutor`), streaming, cancellation, and usage tracking. Loop types are domain-specific strategies that add prompt structure, output schemas, and control flow variants (iterative retrieval, two-phase review) on top of this infrastructure.
- **ClassificationLoop**: Extends SDK's `BaseLoop`. Runs a single `Agent.run()` call with a structured classification system prompt. No tools. Produces `ContextEnhancedQuery` + `ModeDecision`.
- **ExplorationLoop**: Extends SDK's `BaseLoop`. Overrides the loop to add gap-identification and sufficiency-evaluation logic between iterations. Uses SDK `Tool` objects for Enhanced Context Retrieval. Produces `DigestedInformation`.
- **Direct SDK BaseLoop Usage**: Task Analyzer, Task Assessor, and any other straightforward single-input/single-output agents use `tinycua_sdk.agent.loop.BaseLoop` directly through SDK `Agent.run()`. Schema validation may be applied around the returned output, but no custom loop class is created for this pattern.
- **HybridReviewLoop**: Extends SDK's `BaseLoop`. Two-phase execution: deterministic rules (custom, evaluated before SDK loop) then SDK `Agent.run()` for semantic review. Produces `ReviewerDecision`.
- **SchemaValidator**: Shared component that validates LLM output against type schemas, leveraging the SDK's event/model infrastructure for structured parsing and retry.

---

## Success Criteria

- [ ] **Classification Loop**: A ClassificationLoop extending SDK's `BaseLoop` and using an SDK `Agent` produces `ContextEnhancedQuery` + `ModeDecision` from valid inputs. All three modes (primary_agent, worker, uncertain) are reachable depending on input characteristics.
- [ ] **Exploration Loop**: An ExplorationLoop extending SDK's `BaseLoop` with an Enhanced Context Retrieval SDK `Tool` produces `DigestedInformation` with context_summary and key_points. Iterative retrieval works: the agent can make multiple tool-calling iterations via the SDK's `BaseLoop` before stopping.
- [ ] **Direct SDK BaseLoop Usage**: Task Analyzer and Task Assessor use SDK `BaseLoop` directly (via SDK `Agent.run()`) and produce schema-valid outputs. No custom `LinearAgentLoop`, `SimpleLoop`, or equivalent wrapper exists for these agents.
- [ ] **Hybrid Review Loop**: A HybridReviewLoop composing SDK's `BaseLoop` with deterministic checks produces all four `ReviewerDecision` statuses. Deterministic validation failures result in `escalate_user` or `replan` rather than `retry`.
- [ ] **SDK Integration**: All custom loop strategies integrate with `tinycua_sdk` — they extend or compose with `BaseLoop`, use `Agent` for LLM interaction, use SDK `Tool` objects for tool definitions, and use SDK `LanguageModel`/`LLMClient` for provider communication. Standard single-output agents use SDK `BaseLoop` directly. No custom LLM backend protocols, no custom tool dataclasses, no standalone retry or streaming logic.
- [ ] **Error Handling**: Transient LLM failures trigger retry via SDK's built-in infrastructure. Permanent failures and exhausted retries raise typed exceptions. Output validation failures trigger LLM retry with error context, then raise on exhaustion.
- [ ] **Test Coverage**: Unit test coverage exceeds 85% for the loop module, using SDK mock patterns (mock `Agent`, mock `BaseLoop`, mock `LLMClient`).

---

## Testing Plan

### Unit Tests

- Each loop type: construction with SDK `Agent` configuration, construction with invalid config (expected error).
- ClassificationLoop: output matches ModeDecision schema for all three modes. Anti-laziness safeguards produce correct rationales. Edge: all scores low → `uncertain` with non-null `uncertain_next_action`. Verify that no custom LLM backend is created — only SDK `Agent` is used.
- ExplorationLoop: produces DigestedInformation structure. Handles empty retrieval results (fills known_gaps). Makes multiple retrieval iterations via SDK's `BaseLoop` tool-calling. Stops when gaps are addressed. Verifies integration with SDK `Tool` objects.
- Direct SDK BaseLoop usage: Task Analyzer and Task Assessor configurations use SDK `Agent.run()` with SDK `BaseLoop`, produce correct output schemas, and reject invalid input types. With SDK `Tool` objects: use tools via the SDK's tool-calling loop. Without tools: pure reasoning output. Verify that no custom loop class is introduced for this pattern.
- HybridReviewLoop: produces all four status values. Deterministic checks fire before LLM phase. Deterministic failure on schema invalidity cannot be overridden by LLM semantic review. Context updates computed on `accepted`. Retry instructions included on `retry`. LLM review uses SDK's `Agent.run()`.
- SchemaValidator: accepts valid output, rejects invalid output with descriptive error. Validates nested structures (Task tree with child_tasks).
- SDK integration: verify that custom loops do NOT define their own `LLMBackend` protocol, `ToolDef` dataclass, or standalone LLM-calling/rety/streaming logic.

### Integration Tests

- Loop with real (mock-compatible) SDK `Agent` produces correctly structured output for each type.
- ExplorationLoop with an SDK `Tool` for Enhanced Context Retrieval performs multi-step iteration via `BaseLoop`.

### Manual Tests

- None in scope — fully covered by unit and integration tests with mocked SDK `Agent` and `BaseLoop`.

---

## Future Architecture Documentation Sync

Do **not** update `src/tinycua/docs/architecture/` as part of this spec-only PR. During the implementation phase, update architecture documentation to align terminology and mappings with this spec:

- `src/tinycua/docs/architecture/overview.md` → Agent Loop Types table should map Task Analyzer and Task Assessor to direct SDK `BaseLoop` usage rather than a separate Linear/Simple/custom loop type.
- `src/tinycua/docs/architecture/task-analysis.md` → clarify that Task Analyzer uses an SDK `Agent` with the default SDK `BaseLoop`; any single-output guarantee comes from prompt/schema validation, not a custom loop class.
- `src/tinycua/docs/architecture/task-assessor.md` → clarify that Task Assessor uses an SDK `Agent` with the default SDK `BaseLoop`; decomposition-selection output is schema-validated outside the loop.
- Any architecture references to "input→output loop", "linear loop", or "simple loop" should be reviewed and normalized to "SDK BaseLoop direct usage" where no custom control flow is required.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Classification Loop | TODO | |
| Exploration Loop | TODO | |
| Direct SDK BaseLoop mapping | TODO | Standard single-output agents use SDK `BaseLoop`; no custom loop class |
| Hybrid Review Loop | TODO | |
| Uniform BaseLoop integration | TODO | |
| SchemaValidator with SDK retry | TODO | |
| Architecture docs sync (future implementation phase) | TODO | Documented here only; do not update architecture docs in this PR |
| Unit tests | TODO | |

---

## Open Questions

1. **Should standard single-input/single-output agents use a custom Linear/Simple loop or the SDK BaseLoop directly?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-02
   - **Status**: Resolved
   - **Answer**: Use SDK's `BaseLoop` directly. It already provides the shared ReAct/tool-calling infrastructure. Task Analyzer, Task Assessor, and similar agents should be configured as SDK `Agent`s with `BaseLoop`; output schema validation can wrap the result without introducing a new loop type.

2. **Should the Exploration Loop's stop condition be LLM-judged ("has enough information") or count-based (max N iterations)?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-02
   - **Status**: Discussion
   - **Proposed Answer**: Both — LLM judges sufficiency each iteration, but the SDK's `BaseLoop.max_iterations` provides a hard cap to prevent infinite loops.

3. **Should the Hybrid Review Loop's deterministic checks be pluggable rules or hardcoded into the loop implementation?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-02
   - **Status**: Discussion
   - **Proposed Answer**: Pluggable rules registered at construction time, so different reviewers can have different deterministic checks without subclassing the loop.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
