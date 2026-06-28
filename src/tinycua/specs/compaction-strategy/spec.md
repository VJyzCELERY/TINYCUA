# Feature Specification: CompactionStrategy Contract (Milestone 1.3)

**Status**: Draft
**Created**: 2026-06-06
**Last Updated**: 2026-06-06
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Define the `CompactionStrategy` class contract and `SimpleCompaction` default implementation, enabling context compaction for TinyCUA sessions when context limits are exceeded.
- **Gaps**: Today `SessionConfig.compaction_strategy` is a placeholder (`Any | None`). There is no strategy contract, no default implementation, and no integration with `Session.compact_context()`. The architecture design docs define compaction behavior but the contract is not yet implemented.
- **Non-Goals**: Advanced/custom compaction strategies beyond `SimpleCompaction`, provider prompt caching optimization, context retrieval or memory systems, node execution logic.
- **Constraints**: Must not modify `tinycua-sdk` public APIs. Must follow design docs in `src/tinycua/docs/design/`. Compaction strategy class must own its own configuration and behavior. `SessionConfig` selects the strategy but does not own compaction behavior.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer configuring a TinyCUA session sets `SessionConfig.compaction_strategy` to a `CompactionStrategy` implementation (or the default `SimpleCompaction`). When a node's session context exceeds `max_context_messages` or `max_context_tokens`, the node calls `session.compact_context()`. The session delegates to the configured strategy, which compacts the selected messages into one assistant-role summary message. The session replaces the compacted window with the summary, and the node continues execution with the reduced context.

### Acceptance Scenarios

1. **Given** a `SessionConfig` with `compaction_strategy=SimpleCompaction()`, **When** a node calls `session.compact_context()` with a message window, **Then** the strategy compacts the messages into one assistant-role summary message.
2. **Given** a `CompactionStrategy` with `compact(messages)`, **When** called with a list of message dicts, **Then** it returns exactly one `{"role": "assistant", "content": "<summary>"}` message.
3. **Given** a `SimpleCompaction` initialized with parent Agent config, **When** `compact()` is called, **Then** it runs a tool-less compaction Agent using the parent config and returns the final response as the summary.
4. **Given** a `SimpleCompaction` with no parent Agent config, **When** `compact()` is called, **Then** it uses documented default fallback configuration.
5. **Given** a session with `session_context` containing system-role messages, **When** a node calls `session.compact_context()`, **Then** system-role messages are excluded from compaction targets by default.
6. **Given** a `SessionConfig` with `compaction_strategy=None`, **When** a node calls `session.compact_context()`, **Then** it returns `None` and no compaction occurs.
7. **Given** a `CompactionStrategy` implementation, **When** `compact()` is called, **Then** the strategy owns its own configuration and behavior independently of `SessionConfig`.

### Edge Cases

- What happens when `compact()` is called with an empty message list? The strategy MUST return an assistant-role message with empty or minimal content.
- What happens when `SimpleCompaction` cannot reach the compaction Agent? The strategy raises `CompactionError` (propagated from the unreachable Agent).
- What happens when `session.compact_context()` is called but no compaction is needed (context within limits)? The method returns `None` without calling the strategy.
- What happens when the compacted summary is longer than the original messages? The strategy is still responsible for producing one assistant-role message; length optimization is implementation-specific.
- What happens when a node passes system-role messages to `compact()`? The strategy processes them; system-role exclusion is the caller's responsibility, not the strategy's.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide `CompactionStrategy` class with method `compact(messages: list[dict]) -> dict`.
- **FR-002**: `CompactionStrategy.compact()` MUST accept a list of message dicts and return exactly one assistant-role message: `{"role": "assistant", "content": "<summary>"}`.
- **FR-003**: `CompactionStrategy` MUST own its own configuration and behavior; `SessionConfig` selects the strategy but does not dictate compaction details.
- **FR-004**: `CompactionStrategy` MAY create/use its own internal Agent for compaction; this is the explicit exception to the "TinyCUALoop does not create internal Agents" rule.
- **FR-005**: System MUST provide `SimpleCompaction` class extending `CompactionStrategy` as the default simple implementation.
- **FR-006**: `SimpleCompaction` MUST inherit parent Agent configuration (model/provider) when available during initialization.
- **FR-007**: `SimpleCompaction` MUST use documented default fallback configuration when no parent Agent config exists.
- **FR-008**: `SimpleCompaction` MUST run a tool-less compaction Agent over selected session messages.
- **FR-009**: `SimpleCompaction` MUST use a simple system instruction stating it is a compaction agent.
- **FR-010**: `SimpleCompaction` MUST return the compaction Agent's final response as one assistant-role message.
- **FR-011**: `Session.compact_context(window: list[dict] | None = None) -> dict | None` MUST select or accept a compactable context window, call the configured strategy, replace that window with the returned assistant summary, and return the summary.
- **FR-012**: `Session.compact_context()` MUST return `None` when no strategy is configured or no compaction is needed.
- **FR-013**: Compaction MUST exclude system-role messages by default; callers/nodes choose what context to pass to the strategy.
- **FR-014**: Compaction MUST summarize context only; node continuation prompts remain node responsibility.
- **FR-015**: `SessionConfig.compaction_strategy` MUST be typed as `CompactionStrategy | None` (replacing the current `Any | None` placeholder).
- **FR-016**: `CompactionStrategy.compact()` MUST raise `CompactionError` on failure, including: (a) internal compaction failures, and (b) unreachable compaction Agent. The `CompactionError` class MUST be defined in `tinycua/compaction/errors.py`.

### Key Entities _(include if feature involves data)_

- **CompactionStrategy**: Abstract base class for context compaction; accepts `messages: list[dict]` and returns one assistant-role summary message.
- **SimpleCompaction**: Default/simple `CompactionStrategy` implementation that runs a tool-less compaction Agent using parent Agent configuration when available.
- **SessionConfig**: Session-level configuration that selects the compaction strategy via `compaction_strategy` field.
- **Session**: State container that invokes compaction through `compact_context()` when context limits are exceeded.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [x] **CompactionStrategy class exists**: `CompactionStrategy` with `compact(messages: list[dict]) -> dict` method.
- [x] **SimpleCompaction class exists**: `SimpleCompaction` extending `CompactionStrategy` with documented behavior.
- [x] **CompactionStrategy contract validated**: `compact()` returns exactly one assistant-role message.
- [x] **SimpleCompaction uses parent config**: Inherits model/provider config when available.
- [x] **SimpleCompaction fallback works**: Uses defaults when no parent config exists.
- [x] **SimpleCompaction runs tool-less Agent**: No tools exposed to compaction Agent.
- [x] **Session.compact_context() works**: Delegates to strategy, replaces context window, returns summary.
- [x] **Session.compact_context() returns None**: When no strategy configured or no compaction needed.
- [x] **SessionConfig typed correctly**: `compaction_strategy: CompactionStrategy | None`.
- [x] **System-role exclusion documented**: Callers responsible for excluding system messages.
- [x] **Unit tests pass**: Tests for CompactionStrategy, SimpleCompaction, Session.compact_context().
- [x] **Integration tests pass**: End-to-end compaction flow with mocked LLM.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `CompactionStrategy` contract: `compact()` returns exactly one assistant-role message.
- `SimpleCompaction` with parent config: Uses inherited model/provider.
- `SimpleCompaction` without parent config: Uses fallback defaults.
- `SimpleCompaction` runs tool-less Agent: No tools in compaction Agent.
- `Session.compact_context()` with strategy: Delegates and replaces context.
- `Session.compact_context()` without strategy: Returns `None`.
- `Session.compact_context()` with explicit window: Uses provided window.
- `SessionConfig.compaction_strategy` typing: `CompactionStrategy | None`.
- Edge case: `compact()` with empty message list.
- Edge case: `compact()` with system-role messages (caller responsibility).
- Error case: `compact()` raises `CompactionError` when Agent is unreachable (FR-016).
- Error case: `compact()` raises `CompactionError` on internal compaction failure (FR-016).

### Integration Tests

- End-to-end: `session.compact_context()` with `SimpleCompaction` and mocked LLM compaction Agent.
- Factory integration: `create_tinycua_agent()` initializes `SimpleCompaction` with parent config.

### Manual Tests _(if applicable)_

- Verify `SimpleCompaction` works with a real local model endpoint.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| CompactionStrategy class | DONE | New abstract base class |
| SimpleCompaction class | DONE | New class extending CompactionStrategy |
| Session.compact_context() | DONE | New method on Session |
| SessionConfig typing | DONE | Update compaction_strategy field type |
| Unit tests | DONE | |
| Integration tests | DONE | |

---

## Open Questions _(optional)_

1. **CompactionStrategy as ABC or Protocol**: Should `CompactionStrategy` be an abstract base class with `@abstractmethod` or a Protocol?
   - **Owner**: @christopher-sebastian
   - **Status**: Resolved
   - **Answer**: Use ABC with `@abstractmethod` for `compact()` to enforce the contract at class definition time. (See design decision #1.)

2. **SimpleCompaction fallback configuration**: What are the documented default fallback values when no parent Agent config exists?
   - **Owner**: @christopher-sebastian
   - **Status**: Resolved
   - **Answer**: Default to SDK default model/endpoint configuration. Document the specific defaults in implementation. (See design line 241.)

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
