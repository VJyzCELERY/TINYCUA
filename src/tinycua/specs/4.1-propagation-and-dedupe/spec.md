# Feature Specification: Propagation and Dedupe

**Status**: In Progress
**Created**: 2026-06-12
**Last Updated**: 2026-06-12
**Subproject(s) Affected**: tinycua (core)
**Milestone**: 4.1 — Propagation and Dedupe

---

## Problem Statement _(mandatory)_

- **Goals**: Provide explicit propagation rules and dedupe logic so node context crosses node/session boundaries correctly, preserving the useful old `Session.terminate_child(...)` behavior while making it explicit and configurable.
- **Gaps**: Currently, there is no formal propagation model. `chat_history` and `session_context` are conflated, and no deduplication exists when context is copied between nodes or sessions. There is no audit trail separate from LLM-reusable context.
- **Non-Goals**: Tool scoping (Milestone 4.2), retry/validation/monitor hooks (Milestone 4.3), streaming/transcript events (Milestone 4.4). This milestone focuses exclusively on propagation rules, segmented context, ChatRecord audit model, and dedupe.
- **Constraints**: Must not modify tinycua-sdk public APIs. Must preserve existing Session/Todo/Task model contracts. Must integrate with existing NodeQueue suspension/prepend behavior from Milestone 1.7.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

When a node completes execution, its session context is propagated according to a `PropagationRule`: the `output_segment` is forwarded to the next node, while the `prior_context` and `input_segment` propagate upward to the parent/root session. A durable `ChatRecord` audit trail is maintained separately from the mutable `session_context`, and duplicates are filtered during propagation.

### Acceptance Scenarios

1. **Given** a node with segmented session context (prior + input + output), **When** the node terminates, **Then** the output segment is forwarded to the next node as input, and the prior + input segments propagate to the parent session.
2. **Given** a `PropagationRule` with `dedupe=True`, **When** a record with a matching `origin_record_id` already exists in the destination, **Then** the duplicate is skipped and the earliest record is kept.
3. **Given** a `PropagationRule` with `chat_history=root`, **When** a node produces output, **Then** a `ChatRecord` is appended to the root session's chat_history.
4. **Given** a `PropagationRule` with `session_context_target=parent_and_root`, **When** a node terminates, **Then** the non-output segment propagates to both parent and root session contexts.
5. **Given** a terminal ResponseNode, **When** the loop finalizes, **Then** the terminal output segment is committed to root session_context and returned to the SDK caller (terminal output exception).
6. **Given** a ChatRecord with `origin_record_id` set, **When** dedupe is applied, **Then** the record is compared by `origin_record_id` (falling back to `record_id`).

### Edge Cases

- What happens when the output segment is empty? → No forwarding occurs; parent propagation still commits prior + input segments.
- How does the system handle a propagation rule with `session_context_mode=none`? → No session context is propagated upward; only chat_history and token_usage propagate per the rule.
- What happens when a record's `origin_record_id` is None? → Dedupe falls back to comparing `record_id`.
- How does the terminal output exception work when ResponseNode suspends to InformationDigester? → The terminal output is not committed until the final ResponseNode output (after digestion resumes), per the terminal output exception contract.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST implement `PropagationRule` with fields: `chat_history`, `session_context_target`, `session_context_mode`, `token_usage`, `failure`, and `dedupe`.
- **FR-002**: System MUST separate `chat_history` (append-only durable audit transcript) from `session_context` (mutable, selected, deduped LLM-reusable context).
- **FR-003**: System MUST implement `ChatRecord` as an append-only audit model with fields: `record_id`, `role`, `record_type`, `content`, `visibility`, `source_node_id`, `source_session_id`, `receiver_node_id`, `receiver_session_id`, `origin_record_id`, `created_seq`, and `metadata`.
- **FR-004**: System MUST support `SessionContextEntry.segment` with values `prior`, `input`, and `output`.
- **FR-005**: System MUST support source/origin IDs (`origin_record_id`, `source_node_id`, `source_session_id`) on both ChatRecord and SessionContextEntry.
- **FR-006**: System MUST implement dedupe logic that compares `origin_record_id` when present, falling back to `record_id`, keeping the earliest existing record.
- **FR-007**: System MUST implement propagation profiles: `transient_legacy`, `natural_termination_legacy`, `mid_progress_legacy`, and `selected_internal_output`.
- **FR-008**: System MUST implement the terminal output finalization exception: terminal ResponseNode output is committed to root session_context and returned to SDK caller, not forwarded to a next node.
- **FR-009**: System MUST support `NodeMessagePolicy.dedupe_by_origin_record_id` to filter the final LLM-bound node input before `build_messages()` returns.
- **FR-010**: System MUST support `PropagationRule.dedupe` to filter writes into parent/root session_context destinations during propagation.

### Key Entities _(include if feature involves data)_

- **PropagationRule**: Configuration controlling what crosses node/session boundaries (chat_history, session_context_target, session_context_mode, token_usage, failure, dedupe).
- **ChatRecord**: Append-only durable audit transcript recording node I/O provenance, user/assistant messages, tool calls/results, and queue lifecycle events.
- **SessionContextEntry**: Session context record with segment metadata (`prior`, `input`, `output`), origin/source IDs, and created sequence.
- **Session**: State container with separate `chat_history` (append-only) and `session_context` (mutable, deduped).

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [x] **PropagationRule implemented**: PropagationRule dataclass with all required fields exists and is configurable per node/session.
- [x] **ChatHistory vs SessionContext separation**: chat_history is append-only audit; session_context is mutable and deduped. They are stored and managed independently.
- [x] **ChatRecord audit model**: ChatRecord with all required metadata fields is created and appended during node execution.
- [x] **Segmented context**: SessionContextEntry supports segment = prior | input | output with source/origin IDs.
- [x] **Dedupe on propagation**: When dedupe=True, duplicate records (by origin_record_id, fallback to record_id) are filtered during propagation.
- [x] **Dedupe on LLM input**: NodeMessagePolicy.dedupe_by_origin_record_id filters duplicates from final LLM-bound input.
- [x] **Terminal output exception**: Terminal ResponseNode output is committed to root session_context and returned to caller, not forwarded. (finalize_terminal_output implemented in propagation.py:260-298)
- [x] **Propagation profiles work**: transient_legacy, natural_termination_legacy, mid_progress_legacy, and selected_internal_output profiles produce expected propagation behavior. (Profiles defined in propagation.py:38-71, tested in test_propagation_profiles_all_defined)
- [x] **Tests pass**: Unit and integration tests validate propagation, dedupe, and audit behavior. (423 tests passing)

---

## Traceability

| Scenario | Requirements Exercised |
|----------|----------------------|
| 1. Node termination propagation | FR-001, FR-004, FR-005, FR-007 |
| 2. Dedupe by origin_record_id | FR-006, FR-010 |
| 3. ChatRecord appended to root chat_history | FR-003, FR-007 |
| 4. session_context_target=parent_and_root | FR-001, FR-004, FR-007 |
| 5. Terminal output exception | FR-008 |
| 6. Dedupe fallback to record_id | FR-006 |

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_propagation_rule_creation`: PropagationRule instantiation with all fields.
- `test_propagation_rule_profiles`: Each profile (transient_legacy, natural_termination_legacy, mid_progress_legacy, selected_internal_output) produces expected field values.
- `test_chat_record_creation`: ChatRecord with all metadata fields.
- `test_chat_record_origin_deduplication`: Dedupe by origin_record_id when present.
- `test_chat_record_id_fallback_deduplication`: Dedupe falls back to record_id when origin_record_id is None.
- `test_segmented_context_creation`: SessionContextEntry with segment = prior | input | output.
- `test_propagation_upward`: On node termination, prior + input segments propagate to parent/root.
- `test_propagation_forwarding`: On node termination, output segment is forwarded to next node.
- `test_terminal_output_exception`: Terminal output is committed to root, not forwarded.
- `test_dedupe_on_propagation`: Duplicate records filtered during propagation when dedupe=True.
- `test_dedupe_on_llm_input`: NodeMessagePolicy.dedupe_by_origin_record_id filters duplicates from LLM input.
- `test_empty_output_segment`: Empty output segment does not cause forwarding errors.

### Integration Tests

- `test_propagation_e2e`: End-to-end: node terminates → parent/root session_context updated → next node receives output segment.
- `test_propagation_with_suspension`: Propagation works correctly with NodeQueue suspension/prepend from Milestone 1.7.
- `test_chat_history_audit_trail`: ChatHistory accumulates across multiple node executions with proper provenance.

### Manual Tests _(if applicable)_

- Verify propagation behavior with a minimal two-node queue and inspect session_context at each step.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| PropagationRule dataclass | Done | |
| ChatRecord model | Done | |
| SessionContextEntry with segment | Done | |
| Propagation logic in NodeQueue/Loop | Done | |
| Dedupe on propagation | Done | |
| Dedupe on LLM input | Done | |
| Terminal output exception | Done | |
| Unit tests | Done | |
| Integration tests | Done | |

---

## Open Questions _(optional)_

1. **Should PropagationRule be per-node or per-session?**
   - **Owner**: @VJyzCELERY
   - **Target**: TBD
   - **Status**: Resolved
   - **Resolution**: Per-node with session-level defaults, allowing nodes to override.

2. **How should propagation interact with compaction?**
   - **Owner**: @VJyzCELERY
   - **Target**: TBD
   - **Status**: Resolved
   - **Resolution**: Compaction operates on session_context; propagation happens after compaction. Compacted records lose their individual entry but chat_history preserves the audit trail. Propagation never re-propagates already-compacted entries.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
- [x] Open questions resolved (OQ #1: per-node with session-level defaults, allowing nodes to override; OQ #2: propagation after compaction, audit trail preserved)
