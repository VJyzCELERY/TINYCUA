# Feature Specification: TinyCUA Handoff Isolation

**Status**: In Progress
**Created**: 2026-06-16
**Last Updated**: 2026-06-17
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Enforce explicit inter-node handoffs so every TinyCUA node activation starts with isolated message context and receives only the input selected for that node.
- **Gaps**: The runtime currently treats `session_context` as a prompt conveyor, duplicates digested information through multiple paths, exposes deterministic controller text to LLM calls, keeps TaskAssessor writable, and invokes tools directly instead of using SDK `ToolExecutor`.
- **Non-Goals**: This does not add an intermediary LLM handoff rewriter, a graph framework, task-specific fields on the generic handoff envelope, or changes to SDK `ToolExecutor` semantics.
- **Constraints**: Keep native workspace tools actionable, keep provider-compatible message roles, use SDK `ToolExecutor` for permission/approval/invocation, and preserve shared durable task state while isolating per-node message context.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A user asks TinyCUA to create local workspace artifacts. QueryAnalyst receives the real user prompt, Digester/Worker/task nodes exchange explicit `NodeHandoff` inputs, and all downstream nodes build their own prompts from only their node instruction, scoped handoff/input, and continuation. TaskExecutor still gets native tools and can create or verify files through SDK-governed tool execution.

### Acceptance Scenarios

1. **Given** arbitrary root/session prior output, **When** a later node prompt is built, **Then** only explicit `NodeInput`/`NodeHandoff` content is included.
2. **Given** AnalysisEffort schedules another pass, **When** TaskAssessor or TaskAnalyzer runs, **Then** controller text such as `Scheduled analysis effort` is not included in the LLM payload.
3. **Given** TaskAssessor assesses unfinished tasks, **When** it decides follow-up analysis is needed, **Then** it emits a generic handoff to TaskAnalyzer and does not mutate task state.
4. **Given** TinyCUA executes a tool, **When** SDK permissions deny or require approval, **Then** SDK `ToolExecutor` governs the result.

### Edge Cases

- Empty or invalid handoff instructions fail validation instead of becoming blank downstream prompts.
- Handoff payloads remain generic dictionaries; task-specific meaning is interpreted by the target node.
- Existing tests that instantiate nodes directly must keep provider-compatible message shapes.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST represent inter-node transfer with a generic `NodeHandoff` envelope.
- **FR-002**: System MUST treat internal handoffs and continuations as assistant-role messages.
- **FR-003**: System MUST create fresh per-node message sessions while sharing durable task state.
- **FR-004**: System MUST NOT automatically transport root/session context into downstream node prompts.
- **FR-005**: System MUST keep TaskAssessor read-only: it may inspect tasks and emit handoffs, but must not mutate task state.
- **FR-006**: System MUST use SDK `ToolExecutor` for tool invocation, permissions, and approval handling.
- **FR-007**: System MUST render structured TinyCUA handoffs as compact safe text/JSON, never Python reprs.
- **FR-008**: System MUST keep TaskExecutor native tools available in both sync and streaming paths.

### Key Entities _(include if feature involves data)_

- **NodeHandoff**: Generic typed envelope carrying `source_node`, optional `target_node`, `instruction`, `payload`, `constraints`, and metadata.
- **NodeInput**: Trusted internal transport envelope for direct node activation input.
- **Session**: Durable root state and fresh per-node message state; root context is not implicit prompt input.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Downstream prompts are isolated**: Later nodes receive only explicit `NodeInput`/`NodeHandoff` plus node-owned continuation.
- [ ] **Controller text is internal**: Deterministic AnalysisEffort text never appears in LLM request messages.
- [ ] **No duplicated digest**: DigestedInformation appears once in the Worker prompt.
- [ ] **TaskAssessor is read-only**: TaskAssessor has no task mutation tools and uses `node_handoff` for TaskAnalyzer instruction.
- [ ] **SDK tools govern execution**: TinyCUA tool calls respect SDK permissions/approval through `ToolExecutor`.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Message contract tests for explicit handoff-only prompts, no controller leakage, and no duplicate digest.
- Tool scope tests for read-only TaskAssessor.
- Tool execution tests proving SDK `ToolExecutor` permission handling is used.

### Integration Tests

- Streaming tests for TaskExecutor native tool resolution and tool evidence.
- Prototype runtime tests for clean task-tree/runtime state.

### Manual Tests _(if applicable)_

- Live notebook run with local OpenAI-compatible server after deterministic tests pass.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Spec/design | In Progress | Defines explicit handoff isolation and loop/node ownership |
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
