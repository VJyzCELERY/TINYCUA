# Feature Specification: WorkerNode Information-Digestion via QueryAnalyst

**Status**: Draft
**Created**: 2026-06-12
**Last Updated**: 2026-06-12
**Subproject(s) Affected**: tinycua (loops/query_analyst, loops/worker, loops/information_digester, loops/task_create)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide the digestion integration path where **QueryAnalyst spawns `InformationDigesterNode`** before routing to **WorkerNode**, so the **Worker receives structured `DigestedInformation`** (not raw user_query) and forwards it to downstream nodes (TaskCreate, TaskAnalyzer, etc.).
- **Gaps**: Today, QueryAnalyst routes directly to WorkerNode without information digestion. Worker receives the raw user query without any structured context gathering or summarization. When digestion is needed (e.g., large session history, task context), the Worker has no pre-digested information to work with.
- **Non-Goals**: This spec does NOT cover:
  - InformationDigesterNode suspension from ResponseNode (covered in Milestone 3.6).
  - The `enhanced_context_retrieval` tool implementation itself (defined in `docs/design/tools/digester.md`).
  - The `digest_information` tool implementation itself.
  - WorkerNode internal routing decision behavior (task_creation, task_recreation, etc.) — only the integration with digested input.
  - Changes to the InformationDigesterNode's internal behavior — only its spawning and propagation contract via QueryAnalyst.
- **Constraints**: Must work without modifying `tinycua-sdk` public APIs. Must use existing `NodeQueue.spawn_after_current()` mechanism to insert InformationDigesterNode before WorkerNode in the queue. DigestedInformation model must follow the target architecture fields defined in `docs/design/models/digested_information.md`. Worker must forward DigestedInformation downstream without dropping the original query fallback.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A user sends a complex request requiring task planning and execution. QueryAnalyst classifies it as a `worker` route. Before dispatching to WorkerNode, QueryAnalyst spawns an InformationDigesterNode that gathers context from the current session. The digester produces `DigestedInformation` and propagates it to the WorkerNode's session_context. WorkerNode receives the digested context instead of raw user query, and forwards the DigestedInformation to TaskCreateNode (or downstream nodes) for task creation/analysis.

### Acceptance Scenarios

1. **Given** a fresh QueryAnalyst that classifies a request as `worker`, **When** it spawns the worker route, **Then** it first inserts an `InformationDigesterNode` before the WorkerNode in the queue, and the digester produces a structured digest that propagates to WorkerNode's session_context before Worker executes.
2. **Given** a QueryAnalyst that reuses an existing WorkerNode (worker already queued), **When** it routes to `worker`, **Then** it spawns InformationDigesterNode before the existing WorkerNode, the digest propagates to the reuse Worker's session_context, and the Worker resumes with digested context.
3. **Given** a WorkerNode that receives `DigestedInformation` in its session_context, **When** it routes to `task_creation`, **Then** it forwards the DigestedInformation along with its decision to TaskCreateNode.
4. **Given** a WorkerNode that receives the fallback digested information (when digester found no useful context), **When** it proceeds with routing, **Then** it sees the original user query preserved in the fallback `DigestedInformation.context_summary`.
5. **Given** a worker route where InformationDigesterNode has already run (digested context already present in session), **When** QueryAnalyst re-enters the worker path, **Then** it does NOT spawn a duplicate InformationDigesterNode.

### Edge Cases

- What happens when InformationDigesterNode fails or exhausts retries? WorkerNode must still receive a fallback containing the original user query — the digester failure must not block the worker path.
- What happens when QueryAnalyst routes to `worker` but the InformationDigester is already queued/spawned? The route handler must detect existing digestion and avoid duplication.
- What happens when the InformationDigesterNode's session has no useful context? It must produce the defined fallback continuation that preserves the original query.
- What happens when WorkerNode enters with no DigestedInformation present (e.g., direct continuation or re-entry)? Worker must handle missing DigestedInformation gracefully (e.g., fall back to raw user_query from session context).

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: QueryAnalyst `worker` route handler MUST spawn an `InformationDigesterNode` before routing to WorkerNode, inserting it via `queue.spawn_after_current()` or appropriate queue mutation before the Worker.
- **FR-002**: QueryAnalyst `worker` route handler MUST detect if `InformationDigesterNode` is already queued or if digested context already exists in the target Worker's session, and MUST NOT spawn a duplicate digester.
- **FR-003**: InformationDigesterNode MUST propagate its output (DigestedInformation) to the WorkerNode's `session_context` before WorkerNode executes, using the selected-output propagation profile targeting the Worker's session.
- **FR-004**: InformationDigesterNode, when spawned by QueryAnalyst (not ResponseNode), MUST create a fresh node session and not inherit the QueryAnalyst session.
- **FR-005**: InformationDigesterNode MUST produce a fallback continuation string containing the original user query when no useful context is found, per `docs/design/loops/information_digester.md`.
- **FR-006**: WorkerNode MUST accept `DigestedInformation` from its `session_context` as its primary input instead of raw user_query, when available.
- **FR-007**: WorkerNode MUST forward the received `DigestedInformation` to downstream nodes (TaskCreateNode, TaskAnalyzerNode, etc.) as part of its `propagate()` output.
- **FR-008**: WorkerNode MUST preserve the original user query within the `DigestedInformation.context_summary` (or fallback field) and ensure downstream nodes can access it.
- **FR-009**: TaskCreateNode MUST accept input that includes `DigestedInformation` from Worker, using it as context for root task creation alongside the original query.
- **FR-010**: DigestedInformation model MUST contain at minimum: `context_summary`, `key_points`, `advisory_instructions`, `constraints`, `known_gaps` fields, per `docs/design/models/digested_information.md`.
- **FR-011**: DigestedInformation model MUST preserve the original user query in a fallback-capable way so downstream nodes always have access to the raw request.
- **FR-012**: All changes MUST work without modifying `tinycua-sdk` public APIs.

### Key Entities _(include if feature involves data)_

- **DigestedInformation**: Structured output from InformationDigesterNode containing context_summary, key_points, advisory_instructions, constraints, known_gaps. Preserves original query in fallback case.
- **InformationDigesterNode**: ProcessNode that gathers context and produces DigestedInformation. Spawned by QueryAnalyst before Worker, or by ResponseNode via suspension.
- **QueryAnalyst (worker route handler)**: DecisionNode route handler that spawns InformationDigesterNode before routing to WorkerNode, with deduplication logic.
- **WorkerNode**: DecisionNode that receives DigestedInformation as its primary input, forwards it to downstream nodes.
- **TaskCreateNode**: ProcessNode that receives DigestedInformation from Worker as context for root task creation.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **QueryAnalyst spawns digester before Worker**: When routing `worker`, an InformationDigesterNode is inserted before the WorkerNode in the queue.
- [ ] **Digest de-duplication**: QueryAnalyst does not spawn a duplicate InformationDigesterNode when digested context already exists or a digester is already queued.
- [ ] **DigestedInformation propagated to Worker session**: The digester's output lands in WorkerNode's `session_context` before Worker executes.
- [ ] **Worker reads DigestedInformation**: WorkerNode uses DigestedInformation from session_context as primary input context.
- [ ] **Worker forwards DigestedInformation downstream**: WorkerNode includes DigestedInformation in its propagate() output for TaskCreateNode / next node.
- [ ] **Fallback preserves original query**: When digester finds no useful context, the fallback continuation contains the original user query verbatim.
- [ ] **TaskCreateNode receives DigestedInformation**: TaskCreateNode input includes DigestedInformation passed through from Worker.
- [ ] **No SDK API changes**: All implementation lives in `tinycua.loops` without modifying `tinycua-sdk`.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_query_analyst_worker_digest.py`: Test that QueryAnalyst worker route handler spawns InformationDigesterNode before WorkerNode in the queue.
- `test_query_analyst_digest_dedup.py`: Test that QueryAnalyst does not spawn duplicate digester when digested context already exists.
- `test_worker_digested_information_input.py`: Test that WorkerNode reads DigestedInformation from session_context when available, falls back to raw query when absent.
- `test_worker_forward_digested_information.py`: Test that WorkerNode propagate() includes DigestedInformation for downstream nodes.
- `test_digested_information_model.py`: Test DigestedInformation dataclass fields, construction, and fallback behavior.
- `test_task_create_digested_information.py`: Test that TaskCreateNode accepts and uses DigestedInformation in its input context.
- `test_information_digester_fallback.py`: Test that digester produces fallback with original query when no useful context found.

### Integration Tests

- Test end-to-end flow: QueryAnalyst → InformationDigester → Worker → TaskCreate with digested information.
- Test that the full flow works with local model configuration.
- Test that digester failure does not block worker path (fallback is used).

### Manual Tests _(if applicable)_

- None required for this milestone — all paths verifiable through automated tests with mock LLM clients.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| QueryAnalyst worker route with digest spawn | TODO | |
| InformationDigesterNode (fresh session, digest propagation) | TODO | |
| DigestedInformation model | TODO | |
| WorkerNode digested input acceptance | TODO | |
| WorkerNode forward digested information | TODO | |
| TaskCreateNode digested context | TODO | |
| Fallback behavior | TODO | |
| Deduplication logic | TODO | |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **Deduplication strategy**: When QueryAnalyst routes to an existing WorkerNode that already has digested context in its session, how should we detect this? Option A: Check `session_context` for existing `DigestedInformation` entries. Option B: Track a flag in the Queue or Loop. Option C: Check if InformationDigesterNode is already in the queue.
   - **Status**: Decided — Check `session_context` for existing digest entries (Option A). The digester output lands in the session, so checking the owner Worker's session before spawning is the simplest and most reliable approach. Queue position checking is fragile since the digester may have already completed and been removed.

2. **InformationDigesterNode session scope**: When spawned by QueryAnalyst (not ResponseNode), should the digester use a fresh session or inherit QueryAnalyst's root session?
   - **Status**: Decided — Fresh session per `docs/design/loops/information_digester.md`. The digester creates a new session with its own `session_id`, receives selected input from the parent (QueryAnalyst), and accesses root context lazily through `enhanced_context_retrieval`.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices beyond what's in the design docs)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
