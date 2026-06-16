# Feature Specification: TinyCUA Handoff Isolation

**Status**: In Progress
**Created**: 2026-06-16
**Last Updated**: 2026-06-16
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Enforce TinyCUA's documented context-decomposition contract so internal nodes receive focused assistant-role handoffs instead of repeated raw user messages.
- **Gaps**: The runtime currently replays `root_session.input_context` into every node, duplicates handoff content through both queue input and session context, and lets streaming diverge from sync execution for tool/action behavior.
- **Non-Goals**: This does not implement full sub-session isolation, change `src/tinycua-sdk/`, or redesign Worker orchestration from scratch.
- **Constraints**: Preserve the current flat `TinyCUALoop` prototype, keep native workspace tools actionable, keep provider-compatible message roles, and follow the existing docs under `src/tinycua/docs/architecture/` and `src/tinycua/specs/design-simplification/design.md`.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A user asks TinyCUA to create local workspace artifacts. QueryAnalyst receives the real user prompt, routes to Worker, and all downstream nodes receive only structured assistant-role handoffs plus node-specific continuation prompts. TaskExecutor still gets native tools and can create or verify files.

### Acceptance Scenarios

1. **Given** an actionable user request, **When** TinyCUA builds TaskCreate and TaskAnalyzer prompts, **Then** those prompts do not contain the original request as a `role="user"` message.
2. **Given** Digester output is forwarded to Worker or TaskCreate, **When** the next node prompt is built, **Then** the digest appears once as assistant-role compact context.
3. **Given** streaming mode is used, **When** TaskExecutor runs with native tools, **Then** the execution trace records the same resolved tools and tool evidence expected in sync mode.

### Edge Cases

- Passthrough routing must still give ResponseNode enough context to answer without replaying raw input as a downstream user message.
- Fallback task lifecycle state must use structured digest/task state before falling back to raw input.
- Existing tests that instantiate nodes directly must keep provider-compatible message shapes.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST restrict raw external `role="user"` input to the entry boundary by default.
- **FR-002**: System MUST pass internal node handoffs and continuation prompts as `role="assistant"` messages.
- **FR-003**: System MUST append node-specific continuation prompts to internal node LLM calls.
- **FR-004**: System MUST avoid sending the same forwarded output to a node twice through both `NodeInput` and `session_context`.
- **FR-005**: System MUST render structured TinyCUA handoffs as compact safe text/JSON, never Python reprs.
- **FR-006**: System MUST keep TaskExecutor native tools available in both sync and streaming paths.

### Key Entities _(include if feature involves data)_

- **NodeMessagePolicy**: Per-node message selection policy controlling external input inclusion and reusable context.
- **NodeInput**: Trusted internal transport envelope for direct node-to-node handoff.
- **SessionContextEntry**: Durable reusable context/audit data that must not implicitly become user-role input.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Downstream prompts are isolated**: TaskCreate, TaskAnalyzer, and TaskExecutor prompts have no repeated raw `role="user"` request.
- [ ] **Handoffs are assistant-role**: Digester, Worker, TaskCreate, TaskAnalyzer, TaskExecutor, Reviewer, Aggregation, and Response continuation prompts use assistant role.
- [ ] **No duplicated digest**: Forwarded structured output appears once in the next node prompt.
- [ ] **Notebook path stays actionable**: Native file/shell/python tools remain available to TaskExecutor in live and deterministic paths.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Message contract tests for entry-only user input, downstream assistant handoffs, continuation prompts, and duplicate suppression.
- Design gap tests for task lifecycle fallback from digest/task state.

### Integration Tests

- Streaming tests for TaskExecutor native tool resolution and tool evidence.
- Notebook contract tests for clean task-tree/runtime state.

### Manual Tests _(if applicable)_

- Live notebook run with local OpenAI-compatible server after deterministic tests pass.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Spec/design | In Progress | Defines handoff isolation within flat loop |
| Tests | TODO | Add failing contracts before code |
| Implementation | TODO | Enforce policy and continuation prompts |

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
