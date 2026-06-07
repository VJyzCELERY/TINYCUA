# Feature Specification: TinyCUALoop SDK Integration

**Status**: Draft
**Created**: 2026-06-07
**Last Updated**: 2026-06-07
**Subproject(s) Affected**: tinycua (core)
**Milestone**: 1.8 — TinyCUALoop SDK Integration

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a working TinyCUALoop that extends SDK BaseLoop and can execute a minimal node queue without SDK API modifications.
- **Gaps**: TinyCUALoop does not yet exist. The SDK BaseLoop contract is defined but no concrete TinyCUA loop implementation consumes it.
- **Non-Goals**: Concrete node paths (QueryAnalyst, Worker, TaskExecutor, etc.) are deferred to later milestones. Full architecture verification is deferred to Milestone 4.5.
- **Constraints**: Must not modify tinycua-sdk public APIs. Must preserve BaseLoop.run() signature contract. Must consume agent._call_llm() for LLM calls.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer creates a TinyCUA agent using `create_tinycua_agent(...)` and calls `.run(query)`. TinyCUALoop receives the SDK messages, tools, override instructions, and stream mode, then executes a minimal queue containing a stub node and a terminal ResponseNode, returning the final response string.

### Acceptance Scenarios

1. **Given** a TinyCUA agent with TinyCUALoop attached, **When** `.run("hello")` is called, **Then** the loop processes at least one node and returns a string response.
2. **Given** TinyCUALoop receives SDK messages, **When** the loop runs, **Then** messages are merged into the root session input context.
3. **Given** TinyCUALoop receives tools, **When** a node resolves its tool scope, **Then** only allowed tools are visible to that node.
4. **Given** TinyCUALoop receives override_instructions, **When** a node builds its instruction, **Then** override instructions are incorporated.
5. **Given** stream=False, **When** the loop completes, **Then** a final string is returned.
6. **Given** stream=True, **When** the loop runs, **Then** an async iterator of SDK-compatible event dicts is returned.

### Edge Cases

- What happens when the queue is empty after terminal node removal?
- How does the system handle LLM call failures?
- What is the behavior when override_instructions is None?

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: TinyCUALoop MUST extend SDK BaseLoop.
- **FR-002**: TinyCUALoop MUST implement `run(agent, messages, tools, override_instructions, stream)`.
- **FR-003**: TinyCUALoop MUST create and own a root session.
- **FR-004**: TinyCUALoop MUST own a NodeQueue.
- **FR-005**: TinyCUALoop MUST merge SDK messages into root session input context.
- **FR-006**: TinyCUALoop MUST call agent._call_llm() for node LLM calls.
- **FR-007**: TinyCUALoop MUST record chat history and selected session context.
- **FR-008**: TinyCUALoop MUST preserve stream=False final string behavior.
- **FR-009**: TinyCUALoop MUST preserve stream=True async iterator behavior.
- **FR-010**: TinyCUALoop MUST ensure a terminal ResponseNode exists at queue end.
- **FR-011**: TinyCUALoop MUST ensure QueryAnalyst is at queue front (or equivalent entry node).

### Key Entities _(include if feature involves data)_

- **TinyCUALoop**: SDK-compatible execution loop extending BaseLoop.
- **Root Session**: Session owned by TinyCUALoop, holds input context and chat history.
- **NodeQueue**: Sequential queue of nodes to execute.
- **Node**: Abstract unit of work (DecisionNode or ProcessNode).

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Agent.run() works**: `Agent(loop=TinyCUALoop(...)).run(query)` executes without SDK API changes.
- [ ] **Minimal queue execution**: A queue with a stub node and terminal ResponseNode completes.
- [ ] **Message merging**: SDK messages are merged into root session input context.
- [ ] **Tool scoping**: Nodes receive only allowed tools via NodeToolPolicy.
- [ ] **Override instructions**: Nodes incorporate override instructions when present.
- [ ] **Stream=False**: Final string is returned when stream=False.
- [ ] **Stream=True**: Async iterator of SDK events is returned when stream=True.
- [ ] **Chat history**: Node LLM calls are recorded in chat history.
- [ ] **Session context**: Selected session context is recorded.

---

## Testing Plan _(mandatory)_

### Unit Tests

- TinyCUALoop instantiation and BaseLoop extension.
- run() method with stream=False returns string.
- run() method with stream=True returns async iterator.
- Message merging into root session.
- Tool resolution through NodeToolPolicy.
- Override instruction incorporation.
- Queue bootstrapping with terminal node.

### Integration Tests

- End-to-end: create_tinycua_agent(...).run(query) with minimal queue.
- Agent._call_llm() integration with TinyCUALoop.

### Manual Tests _(if applicable)_

- Verify agent runs in a local environment with mock LLM endpoint.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| TinyCUALoop class | TODO | Extends BaseLoop |
| run() implementation | TODO | Handles stream True/False |
| Message merging | TODO | Into root session |
| Queue bootstrapping | TODO | Terminal node guarantee |
| Chat history recording | TODO | Per node LLM call |

---

## Open Questions _(optional)_

1. **What is the default entry node when QueryAnalyst is not yet implemented?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Proposed
   - **Proposed Answer**: Use a minimal stub ProcessNode as placeholder until QueryAnalyst is implemented in Milestone 2.1.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
