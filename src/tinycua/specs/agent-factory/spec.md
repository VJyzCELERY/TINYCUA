# Feature Specification: Agent Factory Contract (Milestone 1.1)

**Status**: Draft
**Created**: 2026-06-05
**Last Updated**: 2026-06-05
**Subproject(s) Affected**: tinycua-backend

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a factory function `create_tinycua_agent(...)` that constructs a working TinyCUA agent backed by the existing SDK `Agent` and `BaseLoop` contracts, enabling the full TinyCUA node-based execution flow to run without SDK API modifications.
- **Gaps**: Today there is no way to instantiate a TinyCUA agent. The architecture exists only as design docs. A factory is the entry point for all downstream milestones (nodes, queue, loop integration).
- **Non-Goals**: Concrete node implementations, WildClawBench adapter, HITL/resume UX, production CLI/TUI, datastore persistence.
- **Constraints**: Must not modify `tinycua-sdk` public APIs. Must integrate via SDK's `Agent(loop=...)` pattern. Must support local model endpoint configuration (Phase 2 — deferred).

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer (or the prototype benchmark harness) calls `create_tinycua_agent(session=None, session_config=None, **agent_kwargs)` and receives back an SDK `Agent` instance with a `TinyCUALoop` attached. Calling `agent.run("some query")` then executes the TinyCUA node queue flow, eventually producing a final response string.

### Acceptance Scenarios

1. **Given** no session provided, **When** `create_tinycua_agent()` is called, **Then** a new root session is created and attached to the loop.
2. **Given** a `SessionConfig` with compaction strategy, **When** the factory is called, **Then** the session uses the configured strategy.
3. **Given** local model endpoint configuration, **When** the factory is called, **Then** the loop can call the local LLM through SDK-compatible execution path. _(Deferred to Phase 2 — FR-006)_
4. **Given** an SDK `Agent` with `loop=TinyCUALoop(...)`, **When** `agent.run("hello")` is called, **Then** the loop processes the query through the node queue and returns a string (or async iterator when streaming).
5. **Given** no SDK API modification, **When** TinyCUALoop runs, **Then** it consumes the existing `Agent._call_llm()` interface for LLM invocations.

### Edge Cases

- What happens when `session` is `None`? A new root session must be created.
- What happens when `session_config` is `None`? Default session behavior (no compaction, no limits) applies.
- What happens when the local model endpoint is unreachable? The loop should propagate the connection error clearly. _(Deferred to Phase 2 — FR-006)_
- What happens when the NodeQueue is empty? `TinyCUALoop.run()` MUST return an empty string and log a warning, allowing the factory to be tested without node implementations.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide `create_tinycua_agent(session=None, session_config=None, **agent_kwargs) -> Agent`.
- **FR-002**: Factory MUST return an SDK `Agent` instance with `loop=TinyCUALoop(...)`.
- **FR-003**: When `session is None`, factory MUST create a new root `Session` and attach it to the loop.
- **FR-004**: When `session` is provided, factory MUST use the provided session.
- **FR-005**: Factory MUST apply `SessionConfig` to the generated/provided session.
- **FR-006**: Factory MUST support local model endpoint configuration. **(Deferred to Phase 2)**
- **FR-007**: `TinyCUALoop` MUST extend SDK `BaseLoop` without modifying SDK public APIs.
- **FR-008**: `TinyCUALoop.run(...)` MUST consume SDK messages, tools, override instructions, and stream mode.
- **FR-009**: `TinyCUALoop.run(...)` MUST call the configured local LLM through SDK-compatible execution path (`agent._call_llm()`). **(M1.1 verifies wiring via mock; real LLM calls in Phase 2)**
- **FR-010**: `TinyCUALoop` MUST record chat history and selected session context.
- **FR-011**: `TinyCUALoop` MUST preserve `stream=False` final string behavior.

### Key Entities _(include if feature involves data)_

- **Agent**: SDK Agent instance — the public-facing entry point for running queries.
- **TinyCUALoop**: SDK BaseLoop extension — owns the root session and NodeQueue, orchestrates node execution.
- **Session**: Root session — stores session context, chat history, task/todo state, and SessionConfig.
- **SessionConfig**: Session-level configuration — compaction strategy, context limits, metadata.
- **NodeQueue**: Ordered list of nodes — drives sequential execution with the current node at index 0.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Factory returns Agent**: `create_tinycua_agent()` returns an SDK `Agent` with `TinyCUALoop` attached.
- [ ] **New session creation**: When no session is provided, a new root session is created.
- [ ] **SessionConfig application**: Provided `SessionConfig` is applied to the session.
- [ ] **Local model support**: Deferred to Phase 2 (see FR-006).
- [ ] **Loop runs without SDK changes**: `agent.run("hello")` executes without modifying SDK public APIs.
- [ ] **Stream mode preserved**: `stream=True` returns async iterator; `stream=False` returns string.
- [ ] **Chat history recorded**: Loop records messages in session chat history.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Factory creates Agent with TinyCUALoop when called with defaults.
- Factory creates new session when `session=None`.
- Factory uses provided session when `session` is given.
- Factory applies SessionConfig to session.
- TinyCUALoop extends BaseLoop (isinstance check).
- TinyCUALoop.run() returns string when `stream=False`.

### Integration Tests

- End-to-end: `create_tinycua_agent().run("hello")` completes without error (mocked LLM).
- Session state is populated after a run (chat history, context entries).

### Manual Tests _(if applicable)_

- Verify factory output with a real local model endpoint. _(Phase 2 — deferred with FR-006)_

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Factory function | TODO | |
| TinyCUALoop class | TODO | |
| Session creation | TODO | |
| SessionConfig integration | TODO | |
| Local model config | Deferred | Phase 2 (see FR-006) |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **Factory parameter passing**: Should factory kwargs map directly to `Agent.__init__` kwargs, or use a separate config object?
   - **Status**: Decided
   - **Decision**: Use `**agent_kwargs` pass-through to keep factory flexible. Resolved in design.md Technical Decision #1.

2. **Default model selection**: What is the default model/endpoint when none is configured?
   - **Status**: Decided
   - **Decision**: Require explicit endpoint configuration; no implicit defaults. The factory raises a clear error when no model/endpoint is configured.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices) — _covered by design.md_
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
