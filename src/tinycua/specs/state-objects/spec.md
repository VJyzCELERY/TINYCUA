# Feature Specification: State Objects (M1)

**Status**: Complete
**Created**: 2026-05-30
**Last Updated**: 2026-06-02
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Provide canonical Python data types for all TINYCUA state objects so internal agents can produce, consume, and serialize typed state consistently.
- **Gaps**: The architecture defines state objects in `src/tinycua/docs/architecture/state-objects.md` as YAML schemas, but there is no Python implementation. Agent code currently has no shared typed representation for Session, ModeDecision, DigestedInformation, TaskTree (Task nodes), TaskResult, ReviewerDecision, WorkerResult, AgentState, ExecutionLog, or WorkerConfig.
- **Non-Goals**: This spec does NOT cover agent factory, custom loop types, system prompts, agent-to-agent calling, session system, worker orchestration, or top-level orchestrator. Those are separate milestones (M3–M10).
- **Constraints**:
  - Types must match the canonical YAML schemas in `src/tinycua/docs/architecture/state-objects.md` after the architecture doc updates defined in the Architecture Doc Synchronization section below are applied.
  - Types must be plain Python.
  - Types must support serialization to/from dict and JSON.
  - All types must be importable from a single public entry point.
  - Types must target Python 3.11+.
  - No runtime LLM dependency for state objects themselves.

---

## User Scenarios & Testing

### Primary Scenario

A developer imports a state object, instantiates it with valid fields, serializes it to JSON, then deserializes it back. The round-trip preserves all data.

### Acceptance Scenarios

1. **Given** a `ModeDecision` object with mode, score, confidence, reasons, and uncertain_next_action, **When** serialized to JSON and back, **Then** the deserialized object matches the original.
2. **Given** a `Task` tree with nested container tasks, **When** serialized to dict, **Then** nesting depth is preserved.
3. **Given** a `ReviewerDecision` with `status=accepted`, **When** validation runs, **Then** it passes without error.
4. **Given** a `ReviewerDecision` with `status=invalid_value`, **When** validation runs, **Then** it raises a validation error.

### Edge Cases

- What happens when optional fields (e.g., `advisory_instructions`, `constraints`) are omitted? They should default to `None`.
- What happens when `uncertain_next_action` is provided but `mode` is not `uncertain`? The value is preserved but downstream consumers should ignore it. When `mode` is `uncertain`, `uncertain_next_action` must be provided.
- What happens with deeply nested `Task` trees? Must handle arbitrary nesting depth.
- What happens when `task_result` is `None` on a leaf? Treated as `not_started` (marker `[ ]`).
- What about negative `consecutive_failures` values? Validation should reject.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a `Session` data type with `session_id`, `owner_type` (enum: primary, child), `owner_name`, `chat_history`, `context`, and `execution_log` fields.
- **FR-002**: System MUST provide a `ContextEnhancedQuery` data type with the enhanced query text.
- **FR-003**: System MUST provide a `ModeDecision` data type with `mode` (enum: primary_agent, worker, uncertain), `score`, `confidence`, `reasons` (list[str]), and `uncertain_next_action` (optional enum: ask_user, explore).
- **FR-004**: System MUST provide a `DigestedInformation` data type with `context_summary`, `key_points` (list[str]), optional `advisory_instructions`, optional `constraints` (list[str]), optional `known_gaps` (list[str]).
- **FR-005**: System MUST provide a `WorkerConfig` data type with `effort` (enum: none, high).
- **FR-006**: System MUST provide a `Task` tree node data type with `task_id`, `parent_task_id` (auto-set from container), `task_name`, `task_description`, `task_context`, `success_criteria`, `confidence`, `task_result` (`TaskResult | None`, default `None` = not_started), and optional `child_tasks` (list of `Task`, `None` for leaf tasks).
- **FR-007**: System MUST provide navigation and display for the Task tree. `traverse()` finds the next non-completed leaf via DFS pre-order (container completion derived from children). `root()` walks to top-most parent. `at_id(task_id)` navigates by structured `T-{idx}.{subidx}...` IDs from anywhere in the tree. `set_parents()` re-establishes `_parent` object references after deserialization (auto-called by `from_dict`/`from_json`). `display()` outputs DFS pre-order string with status markers: `[ ]` not_started, `[*]` inprogress, `[x]` completed, `[-]` failed, `[/]` blocked. Root hides UUID; children show ID.
- **FR-008**: System MUST provide a `TaskResult` data type with `task_id`, `status` (enum: not_started, inprogress, completed, failed, blocked), `result`, optional `discovered_sequence_issues` (list[str]), optional `uncertainty_notes` (list[str]).
- **FR-009**: System MUST provide a `ReviewerDecision` data type with `task_id`, `status` (enum: accepted, retry, replan, escalate_user), `reason`, `confidence`, optional `context_updates` (list[ContextUpdate]), optional `retry_instructions`.
- **FR-010**: System MUST provide a `WorkerResult` data type with `accepted_results` (list[AcceptedResult]).
- **FR-011**: System MUST provide an `AgentState` data type with `active_agent`, `active_task_id`, `status` (enum: idle, running, blocked, terminated), `resume_target`, `consecutive_failures` (int, non-negative).
- **FR-012**: System MUST provide an `ExecutionLog` data type with a sequence of `ExecutionLogEntry` objects (action, outcome, decision).
- **FR-013**: All types MUST support round-trip serialization to and from dict.
- **FR-014**: All types MUST support round-trip serialization to and from JSON.
- **FR-015**: Validation MUST reject invalid enum values, negative integers for `consecutive_failures`, and missing required fields on construction.
- **FR-016**: System MUST provide a `ContextUpdate` data type with `target_task_id` and `update` fields.
- **FR-017**: System MUST provide an `AcceptedResult` data type with `task_id`, `name`, and `result` fields.
- **FR-018**: System MUST provide an `ExecutionLogEntry` data type with `action`, `outcome`, and optional `decision` fields.

### Key Entities

- **Session**: The unit containing conversation history (`chat_history`), model-loaded context (`context`), and sub-session execution log. Central state container for the entire TINYCUA lifecycle.
- **ModeDecision**: Output of the Query Analyst. Drives routing between Primary Agent mode, Worker mode, and Uncertain mode.
- **DigestedInformation**: Precision-oriented context summary produced by the Information Digester. Consumed by Task Analyzer and Primary Agent.
- **Task Tree**: A tree of `Task` nodes navigated via DFS pre-order traversal. Container tasks hold `child_tasks` but are not executed directly; leaf tasks (`child_tasks=None`) are the executable units. Each leaf carries an optional `TaskResult` (`None` = not_started). Container completion is derived from children — a container is completed when all children are completed. Status is tracked per-task via `task_result.status` (not_started, inprogress, completed, failed, blocked). `Task.display()` flattens the tree into a sequential list with rich status markers.
- **TaskResult**: Output of a single task execution. Status indicates completion, failure, or blocked.
- **ReviewerDecision**: Result Reviewer's judgment on a task result. Drives Worker transitions (accept, retry, replan, escalate).
- **WorkerResult**: Aggregated accepted task results, consumed by Primary Agent for final response.
- **AgentState**: Tracks which internal agent is active and its operational status (idle, running, blocked waiting for user input, or terminated).
- **ExecutionLog**: Record of actions, outcomes, and decisions during sub-session execution.
- **WorkerConfig**: Configuration controlling Worker behavior (effort level).
- **ContextEnhancedQuery**: The user's original query enriched with high-level session context by the Query Analyst. Carried as the enhanced query text.
- **ContextUpdate**: A targeted context modification (`target_task_id` + `update` string) produced by the Result Reviewer when a task result reveals information that should update another task's context.
- **AcceptedResult**: A single accepted task output (`task_id`, `name`, `result`) included in `WorkerResult` for Primary Agent consumption.
- **ExecutionLogEntry**: A single entry in the execution log capturing one action, its outcome, and an optional decision trace.

---

## Success Criteria

- [x] All 11 core state object types (Session, ContextEnhancedQuery, ModeDecision, DigestedInformation, WorkerConfig, Task (tree node), TaskResult, ReviewerDecision, WorkerResult, AgentState, ExecutionLog) plus 3 supporting types (ContextUpdate, AcceptedResult, ExecutionLogEntry) are implemented.
- [x] All types support dict round-trip serialization.
- [x] All types support JSON round-trip serialization.
- [x] Enum fields reject invalid values with a clear error.
- [x] Validation catches negative `consecutive_failures` and missing required fields.
- [x] All types are importable from a single entry point (e.g., `from tinycua.state import ...`).
- [x] Unit test coverage exceeds 90% for state object module.
- [x] Architecture docs (`src/tinycua/docs/architecture/state-objects.md`, `src/tinycua/docs/architecture/session-architecture.md`) are updated to match the implemented Python types (see Architecture Doc Synchronization section below for specific changes needed).
- [x] If drift is detected between implementation and architecture docs, the architecture docs are updated accordingly — but remain at the architecture/design level of abstraction, without incorporating low-level implementation details.

---

## Testing Plan

### Unit Tests

- All data type construction with valid and invalid field values.
- `to_dict()` / `from_dict()` round-trip for every type, including nested structures.
- `to_json()` / `from_json()` round-trip for every type.
- Enum validation: invalid enum values raise appropriate errors.
- Field validation: negative `consecutive_failures`, missing required fields, empty lists where required.
- Nested Task tree serialization with `task_result` round-trips.
- Edge cases: `task_result=None` (not_started), all task_result statuses (not_started, inprogress, completed, failed, blocked), container completion derived from children.
- `Task.traverse()`: DFS pre-order finds next non-completed leaf; walks up from completed nodes.
- `Task.display()`: DFS pre-order with correct `[ ]` `[*]` `[x]` `[-]` `[/]` markers and indentation.

### Integration Tests

- None in scope — these types are data-only, no external dependencies or services.

### Manual Tests

- None in scope — testing is fully covered by unit tests.

---

## Architecture Doc Synchronization

The following architecture docs MUST be updated to match the implemented types:

- `src/tinycua/docs/architecture/state-objects.md`: AgentState status values — change `running | waiting_for_user | terminated` → `idle | running | blocked | terminated`
- `src/tinycua/docs/architecture/session-architecture.md`: Session owner_type values — change `primary | tinycua_internal | future_sub_agent` → `primary | child`, with updated description for parent/child chat history propagation and context isolation rules

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Architecture doc updates | Done | Applied in this PR |
| Core data types | Done | 11 core + 3 supporting types (Task is a tree node, replacing TaskList+Task) |
| to_dict / from_dict | Done | Auto-nested via StateObject base class |
| to_json / from_json | Done | Delegates to dict serialization |
| Validation | Done | Enum checks + non-negative consecutive_failures + task_result status validation |
| Tests | Done | 136 tests, 100% coverage |

---

## Open Questions

1. **Should `ExecutionLogEntry` be a separate public type or an inline dict?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-05-30
   - **Status**: Decided
   - **Proposed Answer**: Separate public type for type safety and serialization consistency.

2. **Should `ContextUpdate` be a separate public type?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-05-30
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
