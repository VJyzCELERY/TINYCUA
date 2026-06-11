# Feature Specification: Mandatory Passthrough and Continuation Routing

**Status**: Draft
**Created**: 2026-06-11
**Last Updated**: 2026-06-11
**Subproject(s) Affected**: tinycua (loops/tinycua_loop, loops/result_reviewer, loops/query_analyst, models/classification)
**Milestone**: 3.3 — Mandatory Passthrough and Continuation Routing
**Design**: ./design.md

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a deterministic continuation routing mechanism so that when `ResultReviewer` decides `open_question`, the next user input reaches the intended ResultReviewer session without LLM rerouting, completing the HITL (human-in-the-loop) continuation path.
- **Gaps**: Milestone 3.2 delivered `TinyCUAResultReviewerNode` with `open_question` decision support and `TinyCUALoop._on_reviewer_open_question()` as a stub that only logs. The `MandatoryPassthrough` model exists in `models/classification.py` and the `QueryAnalyst.check_mandatory_passthrough()` precheck exists, but there is no code that *installs* a `MandatoryPassthrough` directive when `open_question` is decided. The end-to-end flow — ResultReviewer decides `open_question` → MandatoryPassthrough installed → user responds → QueryAnalyst precheck detects passthrough → input forwarded to ResultReviewer → ResultReviewer resumes — is not wired.
- **Non-Goals**: This spec does NOT cover propagation/dedupe (Milestone 4.1), tool scoping (Milestone 4.2), streaming (Milestone 4.4), ResponseNode suspension to InformationDigester (Milestone 3.6), or the full architecture verification gate (Milestone 4.5). It does NOT cover WorkerNode passthrough routing (already implemented in Milestone 2.3) or QueryAnalyst classification improvements.
- **Constraints**: Must not modify `tinycua-sdk` public APIs. Must reuse existing `MandatoryPassthrough` model, `QueryAnalyst.check_mandatory_passthrough()`, and `RouteMap` infrastructure. The passthrough mechanism must be deterministic — user continuation must not depend on LLM classification to reach the correct node.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A TinyCUA agent is executing a task. `ResultReviewer` evaluates the execution result and determines it needs user clarification before proceeding (decision: `open_question`). The system preserves the ResultReviewer as the active continuation target, installs a `MandatoryPassthrough` directive targeting that ResultReviewer's node/session, and the next user response is routed deterministically back to the same ResultReviewer — bypassing LLM classification — so the reviewer can resume with the user's answer.

### Acceptance Scenarios

1. **Given** `ResultReviewer` decides `open_question` for an active task, **When** the loop processes the decision, **Then** a `MandatoryPassthrough` directive is installed targeting the ResultReviewer's node_id and session_id.
2. **Given** a `MandatoryPassthrough` is installed after `open_question`, **When** the user provides a continuation response, **Then** `QueryAnalyst` detects the passthrough in input metadata and forwards the input to the ResultReviewer without LLM classification.
3. **Given** a `MandatoryPassthrough` with a valid `target_session_id`, **When** `QueryAnalyst` runs the precheck, **Then** the session IDs match and the passthrough is accepted.
4. **Given** a `MandatoryPassthrough` with a stale `target_session_id` (session has advanced), **When** `QueryAnalyst` runs the precheck, **Then** the passthrough is invalid and falls back to restart (re-enter LLM classification) per `allow_query_analyst_restart=true`.
5. **Given** a `MandatoryPassthrough` with `allow_query_analyst_restart=false` and a stale `target_session_id`, **When** `QueryAnalyst` runs the precheck, **Then** the continuation is dropped silently.
6. **Given** `ResultReviewer` decides `open_question` and the active task context, **When** the loop processes the decision, **Then** the active task is preserved (not marked done, not removed from the task tree).
7. **Given** `open_question` is decided and the user provides a continuation, **When** ResultReviewer resumes, **Then** the user's response is available in the node input and the reviewer can re-evaluate with the new information.

### Edge Cases

- What happens when `open_question` is decided but the ResultReviewer node is no longer in the queue? The `MandatoryPassthrough` targets a node_id that does not exist — QueryAnalyst falls back to restart.
- What happens when multiple `open_question` decisions occur in sequence? Each decision replaces the previous `MandatoryPassthrough` directive — only the latest is active.
- What happens when the user explicitly restarts (sends a new top-level query) instead of answering the open question? The restart bypasses the passthrough and enters normal QueryAnalyst classification.
- What happens when `open_question` is decided but the loop has no active task? The directive is not installed; the loop falls back to normal behavior.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: On `open_question` decision, `TinyCUALoop` MUST install a `MandatoryPassthrough` directive targeting the ResultReviewer's `node_id` and the ResultReviewer's session `session_id`.
- **FR-002**: The `MandatoryPassthrough` MUST set `allow_query_analyst_restart=true` by default so stale continuations fall back to QueryAnalyst classification rather than being dropped.
- **FR-003**: The installed `MandatoryPassthrough` MUST persist across `run()` invocations and be available to `QueryAnalyst`'s precheck before classification runs.
- **FR-004**: `QueryAnalyst.check_mandatory_passthrough()` MUST detect the installed directive and return it when the session guard matches.
- **FR-005**: When a valid `MandatoryPassthrough` is detected, `QueryAnalyst` MUST forward the user input to the target node/session without LLM classification.
- **FR-006**: The passthrough forwarding MUST preserve the user's continuation input so the target node (ResultReviewer) receives it as its next input.
- **FR-007**: When `target_session_id` is present and does not match QueryAnalyst's current session, the passthrough MUST be treated as stale. With `allow_query_analyst_restart=true`, QueryAnalyst MUST fall back to normal LLM classification. With `allow_query_analyst_restart=false`, the continuation MUST be dropped silently.
- **FR-008**: The active task context MUST be preserved during the passthrough cycle — ResultReviewer stays active with the task context intact.
- **FR-009**: `_on_reviewer_open_question()` MUST be updated from a log-only stub to install the `MandatoryPassthrough` directive.
- **FR-010**: The `MandatoryPassthrough` directive MUST be cleared after a successful forward to prevent stale re-use on subsequent unrelated inputs.
- **FR-011**: System MUST NOT modify `tinycua-sdk` public APIs.
- **FR-012**: The passthrough mechanism MUST work for any node that installs a `MandatoryPassthrough`, not only ResultReviewer — the mechanism is node-agnostic.

### Key Entities _(include if feature involves data)_

- **MandatoryPassthrough**: Deterministic continuation directive (already exists in `models/classification.py`). This milestone adds the *installation* logic that populates the directive when `open_question` is decided.
- **ResultReviewer continuation target**: The active ResultReviewer node/session that receives the user's continuation after passthrough.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Open question installs passthrough**: When ResultReviewer decides `open_question`, a `MandatoryPassthrough` is installed targeting the ResultReviewer's node_id and session_id.
- [ ] **QueryAnalyst detects passthrough**: QueryAnalyst's precheck detects the installed `MandatoryPassthrough` and bypasses LLM classification.
- [ ] **Continuation reaches ResultReviewer**: The user's continuation input is forwarded to the ResultReviewer without LLM rerouting.
- [ ] **Stale guard works**: When `target_session_id` mismatches, the passthrough falls back to restart (allow_query_analyst_restart=true) or silent drop (false).
- [ ] **Active task preserved**: The active task context is not lost during the passthrough cycle.
- [ ] **No SDK changes**: All implementation lives in `tinycua.loops` and `tinycua.models`.
- [ ] **Unit tests pass**: All new and modified node/loop logic has unit tests.
- [ ] **Integration tests pass**: End-to-end open_question → passthrough → continuation path works with mocked LLM.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test `_on_reviewer_open_question` installs `MandatoryPassthrough` with correct target_node_id and target_session_id.
- Test `_on_reviewer_open_question` preserves the active task (task status unchanged).
- Test `_on_reviewer_open_question` sets `allow_query_analyst_restart=True` by default.
- Test `QueryAnalyst.check_mandatory_passthrough` returns valid directive when session IDs match.
- Test `QueryAnalyst.check_mandatory_passthrough` returns None when session IDs mismatch and `allow_query_analyst_restart=True`.
- Test `QueryAnalyst.check_mandatory_passthrough` returns None when session IDs mismatch and `allow_query_analyst_restart=False`.
- Test `QueryAnalyst.__call__` with `MandatoryPassthrough` in input metadata bypasses LLM and returns PASSTHROUGH route.
- Test passthrough forwarding preserves user continuation input in the target node's input.
- Test stale passthrough with `allow_query_analyst_restart=True` falls back to LLM classification.
- Test stale passthrough with `allow_query_analyst_restart=False` drops the continuation.
- Test that the `MandatoryPassthrough` is cleared after successful forward.

### Integration Tests

- Test end-to-end: ResultReviewer decides `open_question` → MandatoryPassthrough installed → user continuation → QueryAnalyst forwards → ResultReviewer resumes.
- Test stale continuation: ResultReviewer decides `open_question` → session advances → user continuation → QueryAnalyst falls back to classification.
- Test multiple open_question decisions: second directive replaces the first.

### Manual Tests _(if applicable)_

- Verify open_question → passthrough → continuation in a local environment with mock LLM endpoint.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| `_on_reviewer_open_question` installation | Designed | Implementation pending — see design.md Phase 1 |
| QueryAnalyst precheck integration | Done | Already implemented in Milestone 2.1 |
| Stale guard behavior | Done | Already implemented in check_mandatory_passthrough |
| Passthrough forwarding to ResultReviewer | Designed | Implementation pending — see design.md Phase 1 |
| Active task preservation | Done | Task context is preserved — _on_reviewer_open_question does not modify the active task |
| Unit tests | Designed | 12 tests written in implementation-plan.md |
| Integration tests | Designed | 2 integration tests in implementation-plan.md |

---

## Open Questions _(optional)_

1. **Should the MandatoryPassthrough be stored on the loop or in root session metadata?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-11
   - **Status**: Resolved
   - **Resolved Answer**: Store as a loop-level field (`_pending_mandatory_passthrough`). `TinyCUALoop.run()` replaces `root_session.input_context` on each invocation, so input_context storage would lose the directive between calls. Loop-level storage survives the reset; injection into QueryAnalyst input metadata happens in `_execute_decision_node()`. See design.md Technical Decision #1.

2. **Should open_question set allow_query_analyst_restart=False to force the user to answer the question?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-11
   - **Status**: Resolved
   - **Resolved Answer**: Default to True for safety — if the user sends a new top-level query instead of answering, QueryAnalyst classifies it normally rather than forcing it to the stale reviewer. See design.md Technical Decision #3.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
