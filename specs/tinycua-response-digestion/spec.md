# Feature Specification: TinyCUA ResponseNode — Optional Information Digestion Request

**Status**: Implemented
**Created**: 2026-06-12
**Last Updated**: 2026-06-12
**Subproject(s) Affected**: tinycua (loops/response_node, loops/information_digester, loops/__init__.py, models/digested_information, config/node_config)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide `TinyCUAResponseNode` with **optional digestion request** so the terminal response node can **suspend when context is insufficient, prepend an `InformationDigesterNode` for targeted context gathering, receive the digest back, and resume synthesis** — completing the suspend/resume path for the response phase of the TinyCUA execution loop.
- **Gaps**: Milestone 3.5 delivered `TinyCUAResponseNode` with basic three-phase execution (context check, optional gathering, synthesis) and `TinyCUAInformationDigesterNode` as a standalone `ProcessNode` for context digestion. However, the **integration contract** between them was not formalized in a spec: when `TinyCUAResponseNode` determines context is insufficient, it must be able to suspend the queue, prepend an `InformationDigesterNode` with `parent=TinyCUAResponseNode`, have the digest propagate back into `TinyCUAResponseNode`'s session context, and then resume synthesis. This integration path exists in code but needs a formal specification.
- **Non-Goals**: This spec does NOT cover the full `EnhancedContextRetrieval` implementation (Milestone 4.2), `digest_information` tool scoping (Milestone 4.2), streaming/transcript events (Milestone 4.4), or propagation/dedupe (Milestone 4.1). It does NOT cover the initial `InformationDigesterNode` construction (that was Milestone 2.5). It does NOT cover result aggregation (Milestone 3.4) or task execution (Milestones 3.1–3.3).
- **Constraints**: Must work without modifying `tinycua-sdk` public APIs. Must follow the existing `ProcessNode` and `NodeQueue` contracts. Must not create circular dependencies between `response_node` and `information_digester` modules. Must implement a `max_digest_attempts` guard to prevent infinite suspend/resume loops. Must use a fresh session for the digester (not inherit parent's session).

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A TinyCUA loop reaches the terminal `TinyCUAResponseNode` after result aggregation. The response node inspects the available context (aggregated result, session context) and finds it insufficient for a high-quality final answer. It sets an internal flag (`_needs_digestion = True`) and returns early. During `on_complete`, the queue suspends the response node and prepends a fresh `TinyCUAInformationDigesterNode` with `parent=TinyCUAResponseNode`. The digester runs its context-gathering and digestion cycle, propagates the `DigestedInformation` back into the parent's `session_context`, and the queue advances. `TinyCUAResponseNode` resumes, finds the context sufficient, and synthesizes the final response.

### Acceptance Scenarios

1. **Given** `TinyCUAResponseNode` has insufficient context (no `AggregatedResult`, empty `session_context`), **When** `__call__` is invoked, **Then** it sets `_needs_digestion = True` and returns a placeholder `LLMResult` with `metadata={"needs_digestion": True}` — without immediately calling `_suspend_for_digestion`.
2. **Given** `_needs_digestion` is `True`, **When** `on_complete(queue, response)` is called, **Then** the node calls `_suspend_for_digestion(context, queue)` which creates a `TinyCUAInformationDigesterNode(parent=self)` and calls `queue.suspend_current_and_prepend([digester])`.
3. **Given** the digester has completed and propagated digest back, **When** `TinyCUAResponseNode` resumes via another `__call__`, **Then** it re-checks context sufficiency and — if now sufficient — synthesizes the final response directly (without a second digestion request).
4. **Given** `max_digest_attempts` has been reached (default: 3), **When** context is still insufficient, **Then** `_suspend_for_digestion` logs a warning and returns without suspending — allowing synthesis to proceed with the available (possibly insufficient) context.

### Edge Cases

- What happens when `digester_enabled` is `False`? `TinyCUAResponseNode` skips the digestion path entirely and falls through to `_gather_context_via_tools`.
- What happens when the digester returns an empty digest? The response node resumes with unchanged context, re-evaluates sufficiency, and either synthesizes a fallback or triggers another digestion attempt (up to `max_digest_attempts`).
- What happens if the queue is `None` during `on_complete`? The suspension cannot proceed; the response node logs a warning and returns without mutation.
- What happens with concurrent digestion requests? The queue model is single-threaded (suspend → prepend → resume), so no concurrent digestion is possible.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: `TinyCUAResponseNode` MUST support three-phase execution: (1) context sufficiency check, (2) optional digestion request or tool-based gathering, (3) final response synthesis.
- **FR-002**: When context is insufficient AND `digester_enabled` is `True`, `__call__` MUST set `_needs_digestion = True` and return a placeholder — NOT immediately suspend.
- **FR-003**: `on_complete` MUST check `_needs_digestion` and, if `True`, call `_suspend_for_digestion` to create an `InformationDigesterNode(parent=self)` and invoke `queue.suspend_current_and_prepend([digester])`.
- **FR-004**: `_suspend_for_digestion` MUST check `max_digest_attempts` (default: 3) and skip suspension if the limit has been reached, logging a warning.
- **FR-005**: `TinyCUAInformationDigesterNode` MUST accept a `parent: ProcessNode | None` parameter and create a **fresh session** (not inherit the parent's session).
- **FR-006**: On completion, `InformationDigesterNode.on_complete` MUST propagate the digest output to the parent's `session_context` via `parent_session.session_context.append(...)` and call `queue.advance()` so the parent resumes.
- **FR-007**: `TinyCUAResponseNode` MUST support resumption after digestion: when called again, it re-evaluates context sufficiency and proceeds to synthesis if sufficient.
- **FR-008**: When `digester_enabled` is `False` and context is insufficient, `TinyCUAResponseNode` MUST fall through to `_gather_context_via_tools` (placeholder in M3.6, full implementation deferred).
- **FR-009**: The system MUST provide metadata config keys `digester_enabled` (bool, default `True`), `max_digest_attempts` (int, default `3`), and `sufficiency_threshold` (int, optional) in `NodeConfigBase.metadata`.

### Key Entities

- **`TinyCUAResponseNode`**: Terminal `ProcessNode` that produces the final user-facing response. Supports optional digestion suspension when context is insufficient.
- **`TinyCUAInformationDigesterNode`**: Non-terminal `ProcessNode` that gathers and digests context. Created by `TinyCUAResponseNode._suspend_for_digestion` with `parent=ResponseNode`.
- **`ResponseContext`**: Value object aggregating `AggregatedResult`, `session_context`, `latest_output`, and `continuation_payload` for context sufficiency evaluation.
- **`DigestedInformation`**: Structured output from the digester containing `context_summary`, `key_points`, `advisory_instructions`, `constraints`, and `known_gaps`.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

Objective, measurable checks that prove the problem is solved.

- [x] **`TinyCUAResponseNode` sets `_needs_digestion` flag**: When `__call__` receives insufficient context and `digester_enabled=True`, the flag is set and a placeholder is returned.
- [x] **`on_complete` triggers suspension**: When `_needs_digestion=True`, `on_complete` calls `_suspend_for_digestion` which creates a digester and suspends the queue.
- [x] **Digester creates fresh session**: `TinyCUAInformationDigesterNode.__call__` creates a new `Session()` if none exists.
- [x] **Digest propagates back**: After the digester completes, `on_complete` appends digest to the parent's `session_context` and calls `queue.advance()`.
- [x] **`TinyCUAResponseNode` resumes**: After the queue advances back to the response node, `__call__` re-evaluates context sufficiency and synthesizes the response.
- [x] **`max_digest_attempts` enforced**: After N failed digestion cycles, suspension is skipped and synthesis proceeds with available context.
- [x] **`digester_enabled=False` path**: When the flag is `False`, `TinyCUAResponseNode` skips digestion and falls through to `_gather_context_via_tools`.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `TestTinyCUAResponseNodeInit` — constructor sets initial state (`_needs_digestion=False`, `_digest_attempts=0`)
- `test__check_context_sufficiency` — verifies sufficiency logic for various `ResponseContext` states
- `test__suspend_for_digestion_creates_digester` — verifies digester creation and queue mutation
- `test__suspend_for_digestion_max_attempts` — verifies the max-attempts guard
- `test__gather_context_via_tools_placeholder` — verifies the tool-fallback path

### Integration Tests

- `TestResponseNodeDigesterIntegration` — end-to-end: `__call__` with insufficient context → `on_complete` triggers suspension → digester produces digest → digest propagates → response node resumes
- `TestResponseNodeDirectSynthesis` — `__call__` with sufficient context synthesizes directly (no digestion)
- `TestResponseNodeContinuationRouting` — consolidated continuation path
- `TestResponseNodeRetryBehavior` — retry compliance
- `TestResponseNodeTerminalNormalization` — output normalization

### Manual Tests _(if applicable)_

- N/A — all testing is automated via unit and integration tests.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Three-phase execution in `TinyCUAResponseNode.__call__` | Done | Implemented in `response_node.py` |
| Context sufficiency check (`_check_context_sufficiency`) | Done | Primary + secondary checks |
| Digester suspension (`_suspend_for_digestion`) | Done | Creates digester, calls `queue.suspend_current_and_prepend` |
| `on_complete` digester trigger | Done | Checks `_needs_digestion`, calls `_suspend_for_digestion` |
| `TinyCUAInformationDigesterNode` | Done | Fresh session, digest production, parent propagation |
| Digest propagation to parent | Done | Via `on_complete` → `parent_session.session_context.append` |
| `max_digest_attempts` guard | Done | Configurable via metadata, default 3 |
| `digester_enabled=False` fallback | Done | Falls through to `_gather_context_via_tools` |
| Integration tests | Done | `test_response_node_integration.py` has digester suspension test |

---

## Open Questions _(optional)_

1. **Should the digester receive the parent's full `session_context` or a selected subset?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-15
   - **Status**: Resolved — per FR-005 (fresh session, not inherited) and design decision #2 (parent passes selected context via `NodeInput`), the digester receives only selected context via `NodeInput(messages=...)`.
   - **Proposed Answer**: Selected subset — the parent `TinyCUAResponseNode` should pass only relevant context messages via `NodeInput(messages=...)`, not the entire session context, to keep the digester scoped and focused.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
