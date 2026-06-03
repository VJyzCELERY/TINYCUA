# Feature Specification: TinyCUA Design Simplification — Documentation Reorganization

**Status**: In Progress
**Created**: 2026-06-04
**Last Updated**: 2026-06-04
**Subproject(s) Affected**: tinycua docs, tinycua architecture roadmap drafts

---

## Problem Statement _(mandatory)_

- **Goals**: Reorganize `src/tinycua/docs/design/` so it describes the planned TinyCUA architecture as a SDK-compatible `TinyCUALoop` running a sequential `NodeQueue` of TinyCUA-specific nodes, and produce a reviewable implementation roadmap draft that traces future implementation work back to the design docs.
- **Gaps**: Current design docs describe a multi-layer graph architecture (`AgentGraph`, `RouterNode`, `AgentNode`, per-agent `AgentLoop`s, and worker subgraphs). The new design should simplify this into one SDK `Agent` configured with a `TinyCUALoop`, while preserving the useful behavior of the old graph/session propagation model.
- **Non-Goals**:
  - No runtime implementation in this PR.
  - No source code changes in this PR.
  - No tests in this PR.
  - No SDK modification or SDK API redesign.
  - No TUI, CLI, HITL UX, interrupt UX, resume UX, or datastore persistence roadmap scope.
  - No immediate GitHub issue creation; roadmap content is drafted for PR review first.
- **Constraints**:
  - TinyCUA MUST build around the current `tinycua-sdk` contract: `Agent.run(query, messages=None, instructions=None, stream=False, file_attachments=None)` calls `loop.run(agent, messages, tools, override_instructions, stream)`.
  - The final docs MUST not imply SDK changes are needed for TinyCUA architecture implementation.
  - Documentation migration MUST use a create/update/reconcile/cleanup order: create new docs and verify content before deleting old docs.
  - Roadmap drafts MUST live under `docs/roadmap/tinycua_architecture_implementation/` and be treated as temporary review material until converted into real GitHub issues before merge.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A contributor opens `docs/design/README.md`, follows the new reading order, and can understand how to implement TinyCUA as:

```text
SDK Agent
└── TinyCUALoop extends SDK BaseLoop
    └── NodeQueue
        ├── TinyCUAQueryAnalystNode
        ├── TinyCUAInformationDigesterNode
        ├── TinyCUAWorkerNode
        ├── TinyCUATaskAnalyzerNode
        ├── TinyCUATaskAssessorNode
        ├── TinyCUATaskExecutorNode
        ├── TinyCUAResultReviewerNode
        └── TinyCUAResponseNode
```

The same contributor can then open the roadmap draft and see PR-sized, sequential implementation milestones with design-doc coverage for each milestone.

### Acceptance Scenarios

1. **Given** the current graph-oriented docs, **When** this PR is complete, **Then** `docs/design/` documents the TinyCUALoop/NodeQueue architecture without presenting `AgentGraph`, `RouterNode`, `AgentNode`, worker QueryAnalyst, or generic `PrimaryNode` as target runtime concepts.
2. **Given** the current SDK `Agent.run` and `BaseLoop.run` contract, **When** the design docs describe TinyCUA execution, **Then** they show TinyCUA consuming SDK-provided messages, tools, instruction overrides, and stream mode without modifying the SDK.
3. **Given** the old session propagation docs, **When** the new docs describe propagation, **Then** they preserve the old chat history, session context, token usage, and failure propagation semantics as explicit `PropagationRule` profiles.
4. **Given** the roadmap requirement, **When** the docs are finalized, **Then** a roadmap main issue draft exists under `docs/roadmap/tinycua_architecture_implementation/` with sequential PR-sized milestones and design-doc coverage.

### Edge Cases

- SDK caller passes `messages=[...]`: design must acknowledge these messages as SDK-provided input context that TinyCUALoop should merge/record according to session policy with dedupe.
- SDK caller passes `instructions=...`: design must acknowledge the override but preserve TinyCUA node instruction contracts as hardcoded constants plus append-only config.
- SDK caller passes `stream=True`: design must require node LLM/tool events to be streamable to the caller across all nodes.
- A node receives a plain string internally: design must convert it to an assistant-role message unless it is the actual external user entry.
- A user query contains YAML/front-matter-looking text: design must not parse it as trusted internal structured input.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Documentation MUST define `TinyCUALoop` as extending SDK `BaseLoop` and using the current SDK `loop.run(agent, messages, tools, override_instructions, stream)` contract.
- **FR-002**: Documentation MUST state that this PR does not modify `tinycua-sdk` and that future TinyCUA implementation should build around SDK APIs.
- **FR-003**: Documentation MUST describe SDK `Agent.run(..., messages=..., instructions=..., stream=..., file_attachments=...)` compatibility and acknowledge unspecified override behavior conservatively.
- **FR-004**: Documentation MUST define `NodeQueue` as the sequential execution structure replacing graph/subgraph queues.
- **FR-005**: Documentation MUST define `Node`, `DecisionNode`, and `ProcessNode` as base abstractions.
- **FR-006**: Documentation MUST state that concrete runtime nodes are TinyCUA-specific classes with their own config dataclasses.
- **FR-007**: Documentation MUST define `TinyCUAQueryAnalystNode` as the only top-level QueryAnalyst and as a `DecisionNode`.
- **FR-008**: Documentation MUST remove the separate worker QueryAnalyst target concept and fold worker-specific classification into `TinyCUAWorkerNode`.
- **FR-009**: Documentation MUST define `TinyCUAWorkerNode` as a `DecisionNode` with deterministic pre-checks followed by optional LLM decision.
- **FR-010**: Documentation MUST keep `RouteMap` as a DecisionNode-owned dispatch table mapping validated labels to named route handlers.
- **FR-011**: Documentation MUST define `TinyCUAInformationDigesterNode`, `TinyCUATaskAnalyzerNode`, `TinyCUATaskAssessorNode`, `TinyCUATaskExecutorNode`, `TinyCUAResultReviewerNode`, and `TinyCUAResponseNode` as `ProcessNode` subclasses.
- **FR-012**: Documentation MUST use `TinyCUAResponseNode`, not a generic `PrimaryNode`, for final response synthesis.
- **FR-013**: Documentation MUST describe each node as managing its own session/message context, with possible fresh, inherited, reused, or scoped session initialization.
- **FR-014**: Documentation MUST state that queue position controls execution order and does not imply automatic context sharing.
- **FR-015**: Documentation MUST define `NodeInputLike = str | NodeInput | NodePayload | list[dict]` or an equivalent conceptual contract.
- **FR-016**: Documentation MUST define `NodeInput` and `NodePayload` as internal typed transport models based on `StateObject`-style serialization.
- **FR-017**: Documentation MUST state that `NodePayload` and `NodeInput` can convert to assistant-role message dicts and can carry existing `list[dict]` session context.
- **FR-018**: Documentation MUST state that normal internal communication should not rely on YAML/front-matter string parsing.
- **FR-019**: Documentation MUST include injection safety rules: only queue-created `NodeInput`/`NodePayload` is trusted internal structured input.
- **FR-020**: Documentation MUST state that only actual external user input is role `user`.
- **FR-021**: Documentation MUST state that all internal TinyCUA LLM calls, handoffs, continuations, retries, corrections, and monitor continuations are assistant-role continuations.
- **FR-022**: Documentation MUST distinguish `chat_history` as audit trail from `session_context` as deduped reusable LLM context.
- **FR-023**: Documentation MUST allow internal node LLM communication to be logged in chat history with source node metadata.
- **FR-024**: Documentation MUST store only selected, deduped reusable outputs in `session_context`.
- **FR-025**: Documentation MUST preserve old `Session.terminate_child(...)` propagation behavior as explicit `PropagationRule` profiles.
- **FR-026**: Documentation MUST define `PropagationRule` controls for chat history, session context, session context mode, token usage, failure, and dedupe.
- **FR-027**: Documentation MUST define `suspend_current_and_prepend(...)` as a general NodeQueue capability where a node is suspended by remaining in the queue but not at `queue[0]`.
- **FR-028**: Documentation MUST describe `TinyCUAResponseNode` suspending itself to prepend `TinyCUAInformationDigesterNode`, passing response-node session context to the digester, and resuming after propagation.
- **FR-029**: Documentation MUST define append-only instruction, continuation, and retry-continuation customization.
- **FR-030**: Documentation MUST define node-level retry and validation policy while keeping loop mechanics centralized in TinyCUALoop.
- **FR-031**: Documentation MUST retain AgentMonitor/NodeMonitor as an optional transient hook, not a durable queue node by default.
- **FR-032**: Documentation MUST define configurable `NodeToolPolicy` so each node can expose node tools plus none/selected/all outer `Agent(tools=[...])`.
- **FR-033**: Documentation MUST define `NodeStreamPolicy` and require every node's LLM/tool events to be streamable to the caller when `stream=True`.
- **FR-034**: Documentation MUST require `stream=False` to return the final normalized string from `TinyCUAResponseNode`.
- **FR-035**: Documentation MUST include a complete migration table for current `docs/design/` files/groups.
- **FR-036**: Documentation MUST create a reviewable roadmap draft under `docs/roadmap/tinycua_architecture_implementation/` after design docs are finalized.
- **FR-037**: Roadmap draft milestones MUST be sequential and PR-sized by default, with design docs covered, full/partial coverage, contract implemented, contract deferred, expected PR scope, and exit criteria.
- **FR-038**: Roadmap draft MUST avoid sub-issue drafts by default; optional sub-issue draft files are allowed only if a milestone cannot reasonably be PR-sized.
- **FR-039**: Planning docs MUST state the roadmap draft directory is temporary review material to convert into a real GitHub issue and delete before merge unless the user decides otherwise.

### Key Entities

- **TinyCUALoop**: TinyCUA execution loop that extends SDK BaseLoop and processes a NodeQueue.
- **NodeQueue**: Sequential queue where `queue[0]` is active and queued nodes may be prepended, spawned, or advanced.
- **Node / DecisionNode / ProcessNode**: Base execution abstractions for TinyCUA-specific nodes.
- **RouteMap**: DecisionNode-owned dispatch table from decision label to queue mutation handler.
- **NodeInput / NodePayload**: Internal typed input and payload models for safe node-to-node communication.
- **Session / SessionConfig**: Per-node/root state and session-level behavior configuration.
- **PropagationRule**: Explicit policy controlling what moves between node sessions and parent/root sessions.
- **NodeToolPolicy**: Per-node tool scoping policy.
- **NodeStreamPolicy**: Per-node streaming visibility and metadata policy.

---

## Success Criteria _(mandatory)_

- [ ] **Docs describe SDK-compatible architecture**: `docs/design/` explains TinyCUALoop without requiring SDK changes.
- [ ] **Docs remove stale target concepts**: old graph concepts remain only in migration/history context.
- [ ] **Migration is complete**: every current `docs/design/` file/group has a documented disposition.
- [ ] **Roadmap draft exists**: roadmap main issue draft is reviewable under `docs/roadmap/tinycua_architecture_implementation/`.
- [ ] **Roadmap is PR-sized**: milestones are sequential, design-contract-linked, and sized for reviewable implementation PRs.
- [ ] **Docs-only PR**: no source code or test changes are introduced.

---

## Testing Plan _(mandatory)_

### Unit Tests

- None. This PR is documentation-only.

### Integration Tests

- None. This PR is documentation-only.

### Manual Verification

- Verify `docs/design/` file count target is under 30 after cleanup.
- Verify migration table covers all old design docs.
- Search for stale terms and confirm they appear only in migration/history contexts.
- Verify `docs/design/README.md` reading order matches new architecture.
- Verify roadmap draft milestones reference design docs and are PR-sized.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Planning docs rewrite | TODO | Rewrite spec/design/implementation-plan/task from scratch. |
| Docs/design reorganization | TODO | Create/update/reconcile/delete docs. |
| Roadmap draft | TODO | Create reviewable main issue draft after docs/design finalization. |
| Final verification | TODO | Confirm docs-only diff and migration completeness. |

---

## Review Checklist

- [ ] No runtime implementation details beyond conceptual architecture contracts.
- [ ] All mandatory sections completed.
- [ ] Requirements are testable and unambiguous.
- [ ] Scope is clearly bounded with explicit non-goals.
- [ ] SDK-boundary constraint is explicit.
- [ ] Roadmap draft deliverable is explicit.
