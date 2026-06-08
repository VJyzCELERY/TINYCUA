# Feature Specification: RouteMap and Top-Level QueryAnalyst

**Status**: Complete
**Created**: 2026-06-08
**Last Updated**: 2026-06-08
**Subproject(s) Affected**: tinycua (core)
**Milestone**: 2.1 — RouteMap and Top-Level QueryAnalyst
**Design**: ./design.md

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a deterministic entry-point classification and routing system so TinyCUA can dispatch user input to the correct downstream path (passthrough, worker, or uncertain) without relying on ad-hoc stubs.
- **Gaps**: Currently, TinyCUALoop uses a stub ProcessNode as a placeholder entry node. There is no classification, no route dispatch, and no mechanism for continuation routing. The DecisionNode base class exists but lacks a RouteMap integration and concrete QueryAnalyst behavior.
- **Non-Goals**: Worker LLM decisions (Milestone 2.3), TaskCreate/TaskAnalyzer/TaskAssessor nodes (Milestones 2.4–2.7), TaskExecutor/ResultReviewer (Milestone 3.2), aggregation, response synthesis, and full architecture verification (Milestone 4.5).
- **Constraints**: Must not modify tinycua-sdk public APIs. Must reuse existing DecisionNode, NodeQueue, and TinyCUALoop infrastructure. QueryAnalyst must always be the first node in the queue. MandatoryPassthrough must be deterministic (not LLM-dependent).

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer creates a TinyCUA agent using `create_tinycua_agent(...)` and calls `.run("What files are in the project?")`. TinyCUALoop queues `[QueryAnalyst, ..., ResponseNode]`. QueryAnalyst runs deterministic prechecks (mandatory_passthrough), then performs the two-step decision process (analysis → classification → route dispatch). Based on the classification label, the queue routes to the appropriate downstream path (WorkerNode, stays in QueryAnalyst for uncertain, or forwards via passthrough).

### Acceptance Scenarios

1. **Given** a TinyCUA agent with TinyCUALoop and QueryAnalyst at queue front, **When** `.run("Help me write a script")` is called, **Then** QueryAnalyst classifies the input as `worker` and spawns a WorkerNode before the terminal ResponseNode.
2. **Given** QueryAnalyst is active and receives a continuation, **When** the input is ambiguous, **Then** QueryAnalyst classifies as `uncertain` and remains active, waiting for more user input.
3. **Given** a MandatoryPassthrough directive targeting a specific node/session, **When** QueryAnalyst runs, **Then** it forwards the input directly to the target node/session without LLM classification.
4. **Given** a MandatoryPassthrough with a stale target_session_id, **When** QueryAnalyst runs, **Then** it falls back to QueryAnalyst restart (re-enter classification) per `allow_query_analyst_restart`.
5. **Given** a WorkerNode already exists in the queue, **When** QueryAnalyst classifies as `worker`, **Then** it forwards the input to the existing WorkerNode instead of spawning a duplicate.
6. **Given** QueryAnalyst performs the two-step process, **When** classification returns an invalid label, **Then** it retries according to NodeRetryPolicy.

### Edge Cases

- What happens when QueryAnalyst is already active and a new entry is requested? → **Design**: Emit mandatory_passthrough to the active QueryAnalyst rather than duplicating it.
- How does the system handle empty or null user input? → **Design**: Classify as `uncertain`; QueryAnalyst waits for more input.
- What is the behavior when no WorkerNode exists and label is `worker`? → **Design**: Spawn a new WorkerNode before the terminal ResponseNode.
- What happens when the classification label is not in the RouteMap? → **Design**: Retry per NodeRetryPolicy; if exhausted, route to `uncertain` as fallback.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a RouteMap data structure that maps validated decision labels to route handler callables.
- **FR-002**: RouteMap MUST be owned by concrete DecisionNode classes and dispatch based on validated labels.
- **FR-003**: System MUST provide TinyCUAQueryAnalystNode as a concrete DecisionNode at the queue front.
- **FR-004**: TinyCUAQueryAnalystNode MUST classify user input into one of: `passthrough`, `worker`, `uncertain`.
- **FR-005**: QueryAnalyst MUST run mandatory_passthrough precheck before LLM classification.
- **FR-006**: When a valid MandatoryPassthrough exists, QueryAnalyst MUST forward the input to the target node/session deterministically.
- **FR-007**: When MandatoryPassthrough has a stale target_session_id, QueryAnalyst MUST fall back to restart or silent drop per `allow_query_analyst_restart`.
- **FR-008**: QueryAnalyst MUST use the two-step decision process: analysis call → classification call → RouteMap dispatch.
- **FR-009**: The latest valid classification result MUST determine the route label.
- **FR-010**: When routing to `worker`, QueryAnalyst MUST reuse an existing WorkerNode if one is already queued before the terminal ResponseNode.
- **FR-011**: When routing to `worker` with no existing WorkerNode, QueryAnalyst MUST spawn a new WorkerNode before the terminal ResponseNode.
- **FR-012**: When routing to `uncertain`, QueryAnalyst MUST remain active and wait for user continuation.
- **FR-013**: QueryAnalyst MUST be the first node in the queue at all times (queue invariant).
- **FR-014**: QueryAnalyst MUST only be spawned when no active QueryAnalyst exists (deduplication).
- **FR-015**: Invalid or missing route labels MUST retry according to NodeRetryPolicy.
- **FR-016**: QueryAnalyst MUST preserve the original input query for downstream nodes.

### Key Entities _(include if feature involves data)_

- **RouteMap**: Lightweight dispatch table mapping validated labels to route handler callables.
- **DecisionResult**: Return type from DecisionNode with route_label, analysis_response, and classification_response.
- **MandatoryPassthrough**: Deterministic continuation directive with target_node_id, target_session_id, reason, payload, and allow_query_analyst_restart.
- **TinyCUAQueryAnalystNode**: Top-level entry DecisionNode that classifies user input and routes the queue.
- **QueryAnalystResponse**: Output from QueryAnalyst containing the classification result and forwarded input for downstream nodes. *Reserved for Phase 2 — not yet instantiated in the current implementation.*

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [x] **RouteMap dispatch works**: DecisionNode-owned RouteMap maps labels to handlers and dispatches correctly.
- [x] **QueryAnalyst classifies input**: TinyCUAQueryAnalystNode classifies into passthrough/worker/uncertain.
- [x] **MandatoryPassthrough precheck**: Deterministic continuation overrides LLM classification.
- [x] **Two-step decision process**: Analysis call → classification call → dispatch works end-to-end. *Verified at node level and loop level via `_execute_node()` → `node.__call__()` → `node.on_complete()`.*
- [x] **Worker reuse**: Existing WorkerNode is reused when routing to worker. *Verified at node level; loop integration confirmed via RouteMap dispatch.*
- [x] **Worker spawn**: New WorkerNode is spawned when no existing WorkerNode exists. *Verified at node level; loop integration confirmed via RouteMap dispatch.*
- [x] **Uncertain behavior**: QueryAnalyst remains active for uncertain classification. *Queue does not advance when route_label is "uncertain" (loop-level check in `_run_sync()`/`_run_stream()`).*
- [x] **Invalid label retry**: Invalid classification labels retry per NodeRetryPolicy. *Verified at node level via `DecisionNode.__call__()` retry loop.*
- [x] **QueryAnalyst deduplication**: Active QueryAnalyst is not duplicated.
- [x] **Queue invariant**: QueryAnalyst is always the first node in the queue.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_route_map_dispatch`: RouteMap dispatches labels to correct handlers.
- `test_route_map_unknown_label`: RouteMap raises or falls back for unknown labels.
- `test_query_analyst_init`: TinyCUAQueryAnalystNode instantiation with classification labels.
- `test_query_analyst_classifies_worker`: QueryAnalyst classifies input as worker.
- `test_query_analyst_classifies_passthrough`: QueryAnalyst classifies input as passthrough.
- `test_query_analyst_classifies_uncertain`: QueryAnalyst classifies input as uncertain.
- `test_query_analyst_mandatory_passthrough_precheck`: MandatoryPassthrough overrides LLM classification.
- `test_query_analyst_stale_passthrough`: Stale target_session_id triggers fallback.
- `test_query_analyst_worker_reuse`: Existing WorkerNode is reused instead of spawning new one.
- `test_query_analyst_worker_spawn`: New WorkerNode spawned when none exists.
- `test_query_analyst_invalid_label_retry`: Invalid labels trigger retry per NodeRetryPolicy.
- `test_query_analyst_deduplication`: Active QueryAnalyst prevents duplicate spawn.
- `test_query_analyst_preserves_input_query`: Original input is preserved for downstream.

### Integration Tests

- `test_query_analyst_e2e_worker_route`: End-to-end: QueryAnalyst → WorkerNode → ResponseNode.
- `test_query_analyst_e2e_uncertain`: End-to-end: QueryAnalyst → uncertain → user continuation.
- `test_query_analyst_e2e_passthrough`: End-to-end: QueryAnalyst → passthrough → target node.
- `test_query_analyst_queue_bootstrap`: Queue with QueryAnalyst at front and ResponseNode at end.

### Manual Tests _(if applicable)_

- Verify QueryAnalyst routing in a local environment with mock LLM endpoint.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| RouteMap data structure | TODO | Lightweight dispatch table |
| TinyCUAQueryAnalystNode | TODO | Concrete DecisionNode entry point |
| MandatoryPassthrough precheck | TODO | Deterministic continuation routing |
| Two-step decision process | TODO | Analysis → classification → dispatch |
| Worker reuse/spawn logic | TODO | Existing WorkerNode detection and routing |
| QueryAnalyst deduplication | TODO | Prevent duplicate active QueryAnalyst |

---

## Open Questions _(optional)_

1. **Should RouteMap be a separate class or a dict on DecisionNode?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Resolved (2026-06-08)
   - **Proposed Answer**: Separate RouteMap class for clarity and testability. DecisionNode owns a route_map attribute.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
