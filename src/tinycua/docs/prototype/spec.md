# Feature Specification: Agent Factory Contract (Milestone 1.1)

**Status**: Draft
**Created**: 2026-06-05
**Last Updated**: 2026-06-05
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Provide `create_tinycua_agent()` factory function so callers can instantiate a TinyCUA `Agent` with a properly configured `TinyCUALoop`, without modifying SDK APIs.
- **Gaps**: Today there is no factory; callers must manually construct an SDK Agent and attach a TinyCUALoop. This is error-prone and leaks internal wiring details.
- **Non-Goals**: This spec does NOT cover node execution, concrete node implementations, propagation rules, streaming metadata, session persistence, or TUI/CLI/HITL UX.
- **Constraints**: The factory must build around the existing `tinycua-sdk` contract (`Agent`, `BaseLoop`). SDK APIs must not be modified.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A caller invokes `create_tinycua_agent()` with optional `session`, `agent_config`, and `session_config` parameters, and receives back a ready-to-use SDK `Agent` with `TinyCUALoop` attached.

### Acceptance Scenarios

1. **Given** no arguments, **When** `create_tinycua_agent()` is called, **Then** a new `Agent` is returned with a fresh `Session` and default `SessionConfig`.
2. **Given** a `session_config` is provided, **When** `create_tinycua_agent(session_config=config)` is called, **Then** the generated session is initialized according to the `SessionConfig` policy.
3. **Given** an existing `session`, **When** `create_tinycua_agent(session=sess)` is called, **Then** the provided session is used and `SessionConfig` is applied to it.
4. **Given** an `agent_config` is provided, **When** the factory is called, **Then** the config is forwarded to the SDK `Agent` constructor.
5. **Given** the factory returns, **When** the caller inspects `agent.loop`, **Then** it is an instance of `TinyCUALoop`.

### Edge Cases

- What happens when both `session` and `session_config` are provided? SessionConfig policy governs the provided session.
- What happens when `session is None` and `session_config is None`? A default session with default config is created.
- What happens with invalid or incompatible config values? The factory raises a descriptive error.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST expose `create_tinycua_agent(session=None, agent_config=None, session_config=None, ...) -> Agent`.
- **FR-002**: The factory MUST return an SDK `Agent` with `TinyCUALoop` attached as `agent.loop`.
- **FR-003**: When `session is None`, the factory MUST create a new `Session`.
- **FR-004**: The factory MUST apply `SessionConfig` to the generated or provided session according to the documented policy.
- **FR-005**: The factory MUST NOT modify SDK APIs (`Agent`, `BaseLoop`, `Session`).

### Key Entities

- **Agent**: SDK agent instance that owns a loop and runs queries.
- **TinyCUALoop**: TinyCUA's loop implementation extending SDK `BaseLoop`.
- **Session**: Per-invocation state container holding messages, config, and context.
- **SessionConfig**: Configuration object governing session behavior (compaction, tools, messages, etc.).

---

## Success Criteria _(mandatory)_

- [ ] **Factory returns SDK Agent**: `create_tinycua_agent()` returns an `Agent` instance.
- [ ] **Loop attached**: `agent.loop` is an instance of `TinyCUALoop`.
- [ ] **Session created when None**: When no session is provided, a new one is created.
- [ ] **SessionConfig applied**: Provided config is applied to the session.
- [ ] **No SDK modifications**: SDK APIs remain unchanged.
- [ ] **Unit tests pass**: Factory behavior is verified by tests.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test factory with no arguments returns valid Agent with TinyCUALoop.
- Test factory with session_config applies config to new session.
- Test factory with provided session uses that session.
- Test factory with agent_config forwards config to Agent.
- Test factory raises on invalid config.

### Integration Tests

- End-to-end: factory -> agent.run() -> loop executes (stub/mock nodes).

---

## Open Questions _(optional)_

1. **Additional factory parameters**: Are there other parameters beyond `session`, `agent_config`, `session_config` that should be supported?
2. **SessionConfig defaults**: What are the default values for SessionConfig when none is provided?
3. **Error handling strategy**: Should the factory raise exceptions or return Result types for error cases?

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
