# Tasks: State Objects (M1)

Implementation tasks for State Objects (M1). Check off items as completed.

## TDD Phase (Tests First)

- [ ] T-001 Write serialization round-trip tests (defined in implementation-plan.md)
- [ ] T-002 Run serialization round-trip tests — expect RED (failures) since no implementation yet

## Implementation Phase

- [ ] T-003 Update architecture docs (pre-requisite per spec constraint)
  - [ ] T-004 Update `src/tinycua/docs/architecture/state-objects.md` status values
  - [ ] T-005 Update `src/tinycua/docs/architecture/session-architecture.md` owner_type definition
- [ ] T-006 Create `tinycua.state` module scaffold
  - [ ] T-007 Add `tinycua/state/base.py` with `StateObject` serialization helpers
  - [ ] T-008 Add `tinycua/state/__init__.py` with public re-exports
- [ ] T-009 Implement core state dataclasses
  - [ ] T-010 Session, ContextEnhancedQuery, ModeDecision
  - [ ] T-011 DigestedInformation, WorkerConfig
  - [ ] T-012 Task, TaskList, TaskResult
  - [ ] T-013 ContextUpdate, ReviewerDecision
  - [ ] T-014 AcceptedResult, WorkerResult
  - [ ] T-015 AgentState, ExecutionLog, ExecutionLogEntry
- [ ] T-016 Add validation logic for enums and constraints
  - [ ] T-017 Enum value checks in `__post_init__`
  - [ ] T-018 Non-negative `consecutive_failures` enforcement
- [ ] T-019 Wire serialization for nested structures
  - [ ] T-020 Nested `Task` trees and `TaskList`
  - [ ] T-021 ExecutionLog entries

## Testing Phase

- [ ] T-022 Run serialization round-trip tests — expect GREEN (all pass)
- [ ] T-023 Write unit tests for `tinycua.state` types
- [ ] T-024 Run full test suite: `cd src/tinycua && uv run pytest`

## Verification Phase

- [ ] T-025 Review unit test coverage for `tinycua.state` (>90%)
- [ ] T-026 Confirm serialization round-trips for all state objects
- [ ] T-027 Validate error messages for invalid enum values

## Review and Merge

- [ ] T-028 Address review feedback
- [ ] T-029 Merge to base branch (feat/agent-prototype)

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-30*
