# Feature Specification: M3 Agent Custom Loops

**Status**: Draft
**Created**: 2026-06-02
**Last Updated**: 2026-06-02
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Provide a suite of custom SDK `BaseLoop` subclasses — one per TinyCUA agent type — so each agent's LLM execution can access session state, enforce mandatory tool calls with retry, capture structured `AgentState` output, and yield deterministic final-result events, all while preserving the SDK streaming contract.
- **Gaps**: Today, the SDK `BaseLoop` is used directly, which means:
  - No session access during loop execution.
  - No enforcement of mandatory tool calls (classification, digest, verdict, review decision).
  - No structured `AgentState` output — the loop returns raw text.
  - No final-result event to signal loop termination to the orchestrator.
  - No retry/fallback behavior for missing required tool invocations.
- **Non-Goals**: This spec does NOT cover:
  - Agent graph orchestration (Worker routing, node transitions) — that belongs to the orchestration layer.
  - HITL (human-in-the-loop) behavior — this spec defines No-HITL semantics only (retry/replan/blocked/failed, never wait).
  - SDK `BaseLoop` internals — the spec assumes the SDK contract is stable.
  - Tool implementation — tools are assumed to already exist per the M1/M2 deliverables.
  - Streaming event format changes — events are SDK-compatible and must not break existing consumers.
- **Constraints**:
  - Every custom loop MUST extend `ReActLoop` (application-layer base extending SDK `BaseLoop`).
  - Loop code MUST NOT embed instruction strings — all agent instructions live in `constants/instructions.py`.
  - Every loop MUST write its corresponding `AgentState` subclass to `session.agent_state`.
  - Streaming MUST pass through all SDK-normalized events without loss.
  - The standard `run()` signature MUST be: `async def run(self, agent, messages, tools, override_instructions=None, stream=False)` returning `str | AsyncIterator[dict]`.
  - No-HITL: when an agent cannot proceed, the loop must either retry (up to a configurable budget), flag `replan`, mark `blocked`, or mark `failed` — never wait for human input.

---

## User Scenarios & Testing

### Primary Scenario

A Worker orchestrator delegates to QueryAnalyst, which runs inside `Agent(..., loop=QueryAnalystLoop(session))`. The loop classifies the query, writes `QueryAnalystState`, and returns a structured result event. The orchestrator reads the classification and routes accordingly.

### Acceptance Scenarios

1. **Given** a `QueryAnalystLoop` with a configured classification tool, **When** the LLM produces a classification label, **Then** the loop writes `QueryAnalystState` with the label and `failure=0`, yields a `tinycua.final_result` event, and terminates.
2. **Given** a `TaskExecutorLoop` and the LLM uses `UpdateActiveTaskResult` to mark a task completed, **When** the SDK pass ends, **Then** the loop reads the terminal status from `session.task` and writes `TaskExecutorState(status="terminated")`.
3. **Given** a `ResultReviewLoop` and the LLM produces `accept`, **When** the loop terminates, **Then** it writes `ResultReviewerState(decision="accept")` and yields a final-result event.
4. **Given** a `QueryAnalystLoop` and the LLM does NOT call the classification tool, **When** the loop retries up to `max_classification_retries`, **Then** if still missing, it falls back to the first configured label with `failure=1`.
5. **Given** any loop encounters a non-retryable error, **When** retry budget is exhausted, **Then** the loop sets `failure=1` and yields a terminal final-result event — it does NOT block waiting for human input.

### Edge Cases

- What happens when the LLM stream is cancelled mid-execution? The loop must propagate `asyncio.CancelledError`.
- How does the loop handle a tool result that contains an error? The loop observes it for failure accounting and continues.
- What if the LLM returns content-only (no tool calls) for a loop that requires a specific tool? The loop retries with an in-memory prompt up to the budget, then falls back.
- What if `session.task` has no active task when `TaskExecutorLoop` inspects it? The loop writes `status="running"` (non-terminal).
- What happens if a loop yields its final-result event but the orchestrator has already moved on? Each agent node consumes only its own loop's final event — the event is scoped per agent.

---

## Requirements

### Functional Requirements

- **FR-001**: `ReActLoop` MUST extend SDK `BaseLoop`, accept a `Session` in `__init__`, and expose `self.session` to subclasses.
- **FR-002**: Each agent-specific loop MUST extend `ReActLoop` and override `run()` with the standard signature.
- **FR-003**: Each loop MUST observe the SDK response/event stream, capture relevant data (classification, digest, verdict, tool results, final text), and write the corresponding `AgentState` subclass to `self.session.agent_state`.
- **FR-004**: Each loop MUST yield a `tinycua.final_result` event when it reaches a terminal outcome (success, failure, blocked), containing `agent`, `status`, `failure`, and `result` (the `AgentState.to_dict()`).
- **FR-005**: `QueryAnalystLoop` MUST enforce a mandatory `ClassificationTool` call and retry up to `max_classification_retries` if missing, falling back to the first configured label with `failure=1`.
- **FR-006**: `InformationDigestionLoop` MUST enforce a mandatory `digest_information` tool call and retry up to `max_digest_retries` if missing, falling back to a partial `InformationDigesterState` with `failure=1`.
- **FR-007**: `TaskAssessorLoop` MUST enforce a mandatory verdict classification (`analyze` or `stop`) and retry up to `max_verdict_retries` if missing, falling back to `stop` with `failure=1`.
- **FR-008**: `TaskExecutorLoop` MUST observe tool call results and inspect `session.task` after the SDK pass to determine terminal status from the active task's `TaskResult.status`.
- **FR-009**: `ResultReviewLoop` MUST observe the reviewer classification tool result as `decision` (`accept` | `retry` | `replan`), support open-question non-terminal behavior, and optionally retry if decision is missing.
- **FR-010**: `PrimaryAgentLoop` MUST capture the final assistant response text and extract citations from tool results/metadata, then write `PrimaryAgentState`.
- **FR-011**: `TaskAnalyzerLoop` MUST capture the final assistant summary text as `analysis_summary` and observe task tool failures for failure accounting.
- **FR-012**: All loops MUST support both streaming (`stream=True`) and non-streaming (`stream=False`) modes per the SDK contract.
- **FR-013**: All loops MUST support cancellation via `agent.is_cancelled` and propagate `asyncio.CancelledError`.
- **FR-014**: Retry prompts MUST be in-memory only (not appended to `chat_history` or `session.context`) unless the loop explicitly decides to persist them.
- **FR-015**: All agent instructions MUST be defined in `constants/instructions.py` as module-level constants, NOT embedded in loop code.

### Key Entities

- **Session**: The canonical runtime container holding `chat_history`, `context`, `agent_state`, `task`, `todo_list`, and `config`. Passed to every loop at construction.
- **ReActLoop**: Application-layer base loop extending SDK `BaseLoop`. Stores `session`, provides consistent delegation pattern for all agent-specific loops.
- **AgentState (and subclasses)**: State object written by each loop upon termination, capturing the agent's output, status, and failure count. Includes `QueryAnalystState`, `InformationDigesterState`, `TaskAnalyzerState`, `TaskAssessorState`, `TaskExecutorState`, `ResultReviewerState`, `PrimaryAgentState`.
- **Instructions**: String constants in `constants/instructions.py` — one per agent type (e.g., `QUERY_ANALYST_INSTRUCTION`, `TASK_EXECUTOR_INSTRUCTION`). Referenced by name in AgentNode construction but defined and maintained separately from loop code.

---

## Success Criteria

- [ ] **`ReActLoop` exists**: A concrete base class extending `BaseLoop`, accepting `session: Session`, and exposing the standard `run()` signature.
- [ ] **7 agent-specific loops exist**: `QueryAnalystLoop`, `InformationDigestionLoop`, `TaskAnalyzerLoop`, `TaskAssessorLoop`, `TaskExecutorLoop`, `ResultReviewLoop`, `PrimaryAgentLoop`.
- [ ] **Each loop writes the correct `AgentState`**: Verified via unit tests asserting `session.agent_state` after loop termination.
- [ ] **Mandatory tool enforcement works**: Classification, digest, verdict, and review decision are retried up to budget, then fall back with `failure=1`.
- [ ] **Streaming passthrough is preserved**: All SDK-normalized events are yielded during streaming, with no loss or duplication.
- [ ] **No-HITL guarantee**: In every failure scenario (retry exhausted, missing tool, error), the loop terminates with `failure=1` — it never blocks waiting for human input.
- [ ] **Final-result event emitted**: Each terminal loop termination yields `{"type": "tinycua.final_result", ...}`.
- [ ] **Instructions are not in loop code**: All agent instructions are in `constants/instructions.py`.
- [ ] **All tests pass**: Unit and integration tests for each loop.

---

## Testing Plan

### Unit Tests

- Each loop has a unit test that verifies:
  - `run()` writes the expected `AgentState` to `session.agent_state` given controlled LLM responses.
  - Retry logic: missing mandatory tool → retry up to budget → fallback with `failure=1`.
  - Streaming mode yields events including `tinycua.final_result`.
  - Cancellation raises `asyncio.CancelledError`.
  - Non-streaming mode returns final text correctly.
- `ReActLoop` base class tests:
  - Constructor stores `session`.
  - `run()` delegates to SDK super correctly.
- `ResultReviewLoop` specific:
  - Open-question response → no terminal final event emitted.
  - `accept` / `retry` / `replan` → terminal final event emitted.
- `TaskExecutorLoop` specific:
  - Active task `completed` → `status="terminated"`.
  - Active task `inprogress` → `status="running"`.
  - No active task → `status="running"`.

### Integration Tests

- Each loop exercised through a minimal integration test with a mock LLM that produces tool calls and text responses.
- End-to-end: create a `Session`, build an `Agent` with the loop, call `agent.run()`, assert the state written and the final events yielded.
- Streaming integration: assert each SDK event type is present and the final-result event is the last event.

### Manual Tests

- Visual inspection of streamed output for each loop to confirm no events are lost or duplicated.
- Retry behavior with a tool-ignoring mock LLM: confirm retry count and fallback.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| `ReActLoop` base class | TODO | Shared base for all loops |
| `QueryAnalystLoop` | TODO | Classification enforcement |
| `InformationDigestionLoop` | TODO | Digest tool enforcement |
| `TaskAnalyzerLoop` | TODO | Summary + task tool observation |
| `TaskAssessorLoop` | TODO | Verdict enforcement |
| `TaskExecutorLoop` | TODO | Session task inspection + tool observation |
| `ResultReviewLoop` | TODO | Decision + open-question support |
| `PrimaryAgentLoop` | TODO | Final response + citations |
| `constants/instructions.py` | TODO | Move instructions out of loop code |
| Loop output parsing / validation module | TODO | Shared helpers for event inspection |

---

## Open Questions

1. **How should `max_retries` defaults be configured?**
   - **Owner**: @christopher-sebastian
   - **Target**: 2026-06-05
   - **Status**: Discussion
   - **Proposed Answer**: Per-loop defaults in constructor signature (e.g., `max_classification_retries=3`), overridable by `WorkerConfig` or session config.

2. **Should `ReActLoop` expose helper methods for common retry patterns?**
   - **Owner**: @christopher-sebastian
   - **Target**: 2026-06-05
   - **Status**: Discussion
   - **Proposed Answer**: Yes — a `_retry_with_prompt(messages, retry_prompt, max_retries, is_valid_fn)` helper reduces duplication across loops.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
