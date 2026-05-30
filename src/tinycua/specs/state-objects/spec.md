# Feature Specification: State Objects (M1)

**Status**: In Progress
**Created**: 2026-05-30
**Last Updated**: 2026-05-30
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Provide canonical Python data types for all TINYCUA state objects so internal agents can produce, consume, and serialize typed state consistently.
- **Gaps**: The architecture defines state objects in `src/tinycua/docs/architecture/state-objects.md` as YAML schemas, but there is no Python implementation. Agent code currently has no shared typed representation for Session, ModeDecision, DigestedInformation, TaskList, Task, TaskResult, ReviewerDecision, WorkerResult, AgentState, ExecutionLog, or WorkerConfig.
- **Non-Goals**: This spec does NOT cover agent factory, custom loop types, system prompts, agent-to-agent calling, session system, worker orchestration, or top-level orchestrator. Those are separate milestones (M3–M10).
- **Constraints**:
  - Types must match the canonical YAML schemas in `src/tinycua/docs/architecture/state-objects.md`.
  - Types must be plain Python dataclasses (no ORM, no framework dependency).
  - Types must support serialization to/from dict and JSON.
  - All types must live under `tinycua/` package tree, importable as `tinycua.state.*` or similar.
  - No runtime LLM dependency for state objects themselves.

---

## User Scenarios & Testing

### Primary Scenario

A developer imports a state object, instantiates it with valid fields, serializes it to JSON, then deserializes it back. The round-trip preserves all data.

### Acceptance Scenarios

1. **Given** a `ModeDecision` object with mode, score, confidence, reasons, and uncertain_next_action, **When** serialized to JSON and back, **Then** the deserialized object matches the original.
2. **Given** a `TaskList` with nested container tasks, **When** serialized to dict, **Then** nesting depth is preserved.
3. **Given** a `ReviewerDecision` with `status=accepted`, **When** validation runs, **Then** it passes without error.
4. **Given** a `ReviewerDecision` with `status=invalid_value`, **When** validation runs, **Then** it raises a validation error.

### Edge Cases

- What happens when optional fields (e.g., `advisory_instructions`, `constraints`) are omitted? They should default to `None` or empty list.
- What happens when `uncertain_next_action` is provided but `mode` is not `uncertain`? Should be allowed but flagged — or schema should allow it.
- What happens with deeply nested `Task` trees? Must handle arbitrary nesting depth.
- What happens on empty `TaskList` (no tasks)? Valid; no tasks to execute.
- What about negative `consecutive_failures` values? Validation should reject.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a `Session` dataclass with `session_id`, `owner_type` (enum: primary, child), `owner_name`, `chat_history`, `context`, and `execution_log` fields.
- **FR-002**: System MUST provide a `ContextEnhancedQuery` dataclass with the enhanced query text.
- **FR-003**: System MUST provide a `ModeDecision` dataclass with `mode` (enum: primary_agent, worker, uncertain), `score`, `confidence`, `reasons` (list[str]), and `uncertain_next_action` (optional enum: ask_user, explore).
- **FR-004**: System MUST provide a `DigestedInformation` dataclass with `context_summary`, `key_points` (list[str]), optional `advisory_instructions`, optional `constraints` (list[str]), optional `known_gaps` (list[str]).
- **FR-005**: System MUST provide a `WorkerConfig` dataclass with `effort` (enum: none, high).
- **FR-006**: System MUST provide a `TaskList` dataclass containing a list of `Task` objects and a `current_task_id`.
- **FR-007**: System MUST provide a `Task` dataclass with `task_id`, `name`, `description`, `context`, `success_criteria` (list[str]), optional nested `tasks` (list[Task]), and `confidence`.
- **FR-008**: System MUST provide a `TaskResult` dataclass with `task_id`, `status` (enum: completed, failed, blocked), `result`, optional `discovered_sequence_issues` (list[str]), optional `uncertainty_notes` (list[str]).
- **FR-009**: System MUST provide a `ReviewerDecision` dataclass with `task_id`, `status` (enum: accepted, retry, replan, escalate_user), `reason`, `confidence`, optional `context_updates` (list[ContextUpdate]), optional `retry_instructions`.
- **FR-010**: System MUST provide a `WorkerResult` dataclass with `accepted_results` (list[AcceptedResult]).
- **FR-011**: System MUST provide an `AgentState` dataclass with `active_agent`, `active_task_id`, `status` (enum: idle, running, blocked, terminated), `resume_target`, `consecutive_failures` (int, non-negative).
- **FR-012**: System MUST provide an `ExecutionLog` dataclass with a sequence of `ExecutionLogEntry` objects (action, outcome, decision).
- **FR-013**: All dataclasses MUST support `to_dict()` and `from_dict()` serialization.
- **FR-014**: All dataclasses MUST support `to_json()` and `from_json()` serialization (JSON string round-trip).
- **FR-015**: Validation MUST reject invalid enum values, negative integers for `consecutive_failures`, and missing required fields on construction.

### Key Entities

- **Session**: The unit containing conversation history (`chat_history`), model-loaded context (`context`), and sub-session execution log. Central state container for the entire TINYCUA lifecycle.
- **ModeDecision**: Output of the Query Analyst. Drives routing between Primary Agent mode, Worker mode, and Uncertain mode.
- **DigestedInformation**: Precision-oriented context summary produced by the Information Digester. Consumed by Task Analyzer and Primary Agent.
- **TaskList / Task**: Sequential roadmap of work items. Tasks can be container (with nested sub-tasks) or leaf (directly executable).
- **TaskResult**: Output of a single task execution. Status indicates completion, failure, or blocked.
- **ReviewerDecision**: Result Reviewer's judgment on a task result. Drives Worker transitions (accept, retry, replan, escalate).
- **WorkerResult**: Aggregated accepted task results, consumed by Primary Agent for final response.
- **AgentState**: Tracks which internal agent is active and its operational status (idle, running, blocked waiting for user input, or terminated).
- **ExecutionLog**: Record of actions, outcomes, and decisions during sub-session execution.
- **WorkerConfig**: Configuration controlling Worker behavior (effort level).

---

## Success Criteria

- [ ] All 12 state object types (Session, ContextEnhancedQuery, ModeDecision, DigestedInformation, WorkerConfig, TaskList, Task, TaskResult, ReviewerDecision, WorkerResult, AgentState, ExecutionLog) are implemented as Python dataclasses.
- [ ] Every type has `to_dict()` and `from_dict()` methods that produce correct round-trip serialization.
- [ ] Every type has `to_json()` and `from_json()` methods that produce correct JSON round-trip serialization.
- [ ] Enum fields reject invalid values with a clear error.
- [ ] Validation catches negative `consecutive_failures` and missing required fields.
- [ ] All types are importable from a single entry point (e.g., `from tinycua.state import ...`).
- [ ] Unit test coverage exceeds 90% for state object module.
- [ ] Architecture docs (`docs/architecture/state-objects.md`, `docs/architecture/session-architecture.md`) are updated to match the implemented Python types (see Design Updates section below for specific changes needed).
- [ ] If drift is detected between implementation and architecture docs, the architecture docs are updated accordingly — but remain at the architecture/design level of abstraction, without incorporating low-level implementation details.

---

## Testing Plan

### Unit Tests

- All dataclass construction with valid and invalid field values.
- `to_dict()` / `from_dict()` round-trip for every type, including nested structures.
- `to_json()` / `from_json()` round-trip for every type.
- Enum validation: invalid enum values raise appropriate errors.
- Field validation: negative `consecutive_failures`, missing required fields, empty lists where required.
- Nested Task tree serialization (container with multi-level sub-tasks).
- Edge cases: empty `context_updates`, empty `key_points`, empty `known_gaps`, no `uncertain_next_action`.

### Integration Tests

- None in scope — these types are data-only, no external dependencies or services.

### Manual Tests

- None in scope — testing is fully covered by unit tests.

---

## Architecture Doc Updates Required

The following changes must also be applied to the canonical architecture docs to keep them in sync with the implementation:

| Architecture Doc | Change Needed |
|-----------------|---------------|
| `docs/architecture/state-objects.md` (line 242) | `agent_state.status` values: `running \| waiting_for_user \| terminated` → `idle \| running \| blocked \| terminated` |
| `docs/architecture/session-architecture.md` (line 97) | `session.owner_type` values: `primary \| tinycua_internal \| future_sub_agent` → `primary \| child` |
| `docs/architecture/session-architecture.md` (line 104) | Description text: remove reference to `future_sub_agent`; update to reflect `primary \| child` model (parent records own + child chat history, child context isolated from parent, etc.) |

> **Note**: These architecture doc updates are in scope for this implementation and will be applied as part of the work.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Architecture doc updates | TODO | Sync `state-objects.md` and `session-architecture.md` |
| Core dataclasses | TODO | |
| to_dict / from_dict | TODO | |
| to_json / from_json | TODO | |
| Validation | TODO | |
| Tests | TODO | |

---

## Open Questions

1. **Should `ExecutionLogEntry` be a separate public type or an inline dict?**
   - **Status**: Decided
   - **Proposed Answer**: Separate public type for type safety and serialization consistency.

2. **Should `ContextUpdate` be a separate public type?**
   - **Status**: Decided
   - **Proposed Answer**: Yes — `target_task_id` + `update` string as a named struct.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
