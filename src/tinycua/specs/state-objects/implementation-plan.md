# Implementation: State Objects (M1)

Deliver canonical Python dataclasses for all TINYCUA state objects with consistent serialization and validation, so internal agents can reliably exchange typed state.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

**N/A** — no special environment setup required beyond the standard `src/tinycua` project tooling.

---

## Success Criteria — Serialization Round-Trip Tests (TDD First)

Define the serialization round-trip tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/unit/state/test_state_objects_serialization.py
"""Serialization round-trip tests for state objects serialization and validation."""

import pytest

from tinycua.state import ModeDecision, Task, ReviewerDecision


def test_mode_decision_json_round_trip():
    """ModeDecision survives JSON round-trip without data loss."""
    # Arrange
    decision = ModeDecision(
        mode="uncertain",
        score=0.72,
        confidence=0.41,
        reasons=["low context", "conflicting signals"],
        uncertain_next_action="ask_user",
    )
    # Act
    serialized = decision.to_json()
    restored = ModeDecision.from_json(serialized)
    # Assert
    assert restored == decision


def test_task_tree_nested_round_trip_dict():
    """Nested Task tree structures round-trip through dict serialization."""
    # Arrange
    leaf = Task(
        task_id="t-2",
        task_name="leaf",
        task_description="leaf task",
        task_context="ctx",
        success_criteria=["done"],
        confidence=0.9,
    )
    parent = Task(
        task_id="t-1",
        task_name="parent",
        task_description="container task",
        task_context="ctx",
        success_criteria=["all children done"],
        confidence=0.8,
        child_tasks=[leaf],
    )
    # Act
    restored = Task.from_dict(parent.to_dict())
    # Assert
    assert restored == parent
    assert restored.child_tasks[0].task_id == "t-2"


def test_task_tree_nested_round_trip_json():
    """Nested Task tree structures round-trip through JSON serialization."""
    leaf = Task(
        task_id="t-2",
        task_name="leaf",
        task_description="leaf task",
        task_context="ctx",
        success_criteria=["done"],
        confidence=0.9,
    )
    parent = Task(
        task_id="t-1",
        task_name="parent",
        task_description="container task",
        task_context="ctx",
        success_criteria=["all children done"],
        confidence=0.8,
        child_tasks=[leaf],
    )
    restored = Task.from_json(parent.to_json())
    assert restored == parent
    assert restored.child_tasks[0].task_id == "t-2"


def test_reviewer_decision_rejects_invalid_status():
    """ReviewerDecision validation rejects unsupported status values."""
    with pytest.raises(ValueError, match="status"):
        ReviewerDecision(
            task_id="t-1",
            status="invalid_value",
            reason="bad status",
            confidence=0.2,
        )
```

### Key Test Scenarios

- [x] **Scenario 1**: Session dict/JSON round-trip preserves all fields and equality (FR-001, FR-013, FR-014).
- [x] **Scenario 2**: ModeDecision JSON round-trip preserves all fields and equality.
- [x] **Scenario 3**: Task tree with nested container/leaf tasks round-trips via dict serialization.
- [x] **Scenario 4**: Task tree with nested container/leaf tasks round-trips via JSON serialization.
- [x] **Scenario 5**: ExecutionLog with nested ExecutionLogEntry round-trip via dict/JSON (FR-012).
- [x] **Scenario 6**: DigestedInformation with all optional fields omitted (FR-004, edge case).
- [x] **Scenario 7**: AgentState rejects negative `consecutive_failures` (FR-011, FR-015).
- [x] **Scenario 8**: WorkerConfig rejects invalid `effort` value (FR-005).
- [x] **Edge case**: ReviewerDecision rejects an invalid status value with a clear error.

## Verification Plan

### Automated Tests

- [x] Serialization round-trip tests (defined above) — these must pass for implementation to be complete
- [x] Unit tests for `tinycua.state` modules — serialization, validation, edge cases
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`
- [x] Lint check passes: `cd src/tinycua && uv run ruff check .`
- [x] Type check passes: `cd src/tinycua && uv run mypy tinycua/state/`

### Manual Verification

- None — behavior is fully covered by automated tests

### Performance Considerations

- None — data-only types with no performance-sensitive paths

## Proposed Changes

### Documentation (Architecture Docs — Pre-requisite)

#### [MODIFY] src/tinycua/docs/architecture/state-objects.md

- **Description of change**: Update `agent_state.status` values to `idle | running | blocked | terminated`.
- **Rationale**: Aligns canonical schema with implemented literals before code depends on new enum values.

#### [MODIFY] src/tinycua/docs/architecture/session-architecture.md

- **Description of change**: Update `session.owner_type` values and description for `primary | child`.
- **Rationale**: Aligns canonical session ownership model with spec before code depends on new enum values.

### State Objects Module

#### [NEW] src/tinycua/tinycua/state/base.py

- **Description of change**: Introduce `StateObject` base class with `to_dict()` / `from_dict()` / `to_json()` / `from_json()` helpers.
- **Rationale**: Ensures consistent serialization across all state objects.

#### [NEW] src/tinycua/tinycua/state/session.py

- **Description of change**: Add `Session` dataclass with validation for required fields and owner type values.
- **Rationale**: Canonical session container described in the spec.

#### [NEW] src/tinycua/tinycua/state/mode_decision.py

- **Description of change**: Add `ContextEnhancedQuery` and `ModeDecision` dataclasses with enum-value validation.
- **Rationale**: Required for query analysis routing decisions.

#### [NEW] src/tinycua/tinycua/state/digested_information.py

- **Description of change**: Add `DigestedInformation` dataclass with optional fields and defaults.
- **Rationale**: Provides structured context summary payload.

#### [NEW] src/tinycua/tinycua/state/worker_config.py

- **Description of change**: Add `WorkerConfig` dataclass with effort validation.
- **Rationale**: Encodes worker effort level for internal agent control.

#### [NEW] src/tinycua/tinycua/state/task.py

- **Description of change**: Add `Task` tree node dataclass with `task_result`-based status tracking, `parent_task_id` auto-setting, and `display()` DFS pre-order traversal.
- **Rationale**: Represents the internal execution plan and task tree.

#### [NEW] src/tinycua/tinycua/state/task_result.py

- **Description of change**: Add `TaskResult` dataclass with status validation.
- **Rationale**: Captures task execution outcomes.

#### [NEW] src/tinycua/tinycua/state/reviewer.py

- **Description of change**: Add `ContextUpdate` and `ReviewerDecision` dataclasses.
- **Rationale**: Supports review outcomes and context updates.

#### [NEW] src/tinycua/tinycua/state/worker_result.py

- **Description of change**: Add `AcceptedResult` and `WorkerResult` dataclasses.
- **Rationale**: Aggregates accepted task results for primary agent consumption.

#### [NEW] src/tinycua/tinycua/state/agent_state.py

- **Description of change**: Add `AgentState` dataclass with status validation and non-negative `consecutive_failures` enforcement.
- **Rationale**: Tracks internal agent lifecycle state.

#### [NEW] src/tinycua/tinycua/state/execution_log.py

- **Description of change**: Add `ExecutionLog` and `ExecutionLogEntry` dataclasses.
- **Rationale**: Captures per-session execution trace.

#### [NEW] src/tinycua/tinycua/state/__init__.py

- **Description of change**: Re-export all public types and literal aliases for easy import.
- **Rationale**: Provides stable `tinycua.state` API surface.

#### [NOT DONE] src/tinycua/tinycua/__init__.py

- **Description of change**: Optionally re-export `tinycua.state` for discoverability.
- **Rationale**: Decided against — re-export not needed. Discoverability via `tinycua.state` direct import is sufficient.

### Tests

#### [NEW] src/tinycua/tests/unit/state/test_state_objects_serialization.py

- **Description of change**: Serialization round-trip tests that validate cross-object serialization and validation.
- **Rationale**: Ensures end-to-end round-trips and error handling.

#### [NEW] src/tinycua/tests/unit/state/test_state_objects_unit.py

- **Description of change**: Unit tests for each state object and validation rule.
- **Rationale**: Achieve >90% coverage for the state module.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/state/` | New | New module containing all state dataclasses and serialization helpers |
| `tinycua/__init__.py` | Modify | Optional re-export of `tinycua.state` |
| Architecture docs | Modify | Update state object and session ownership definitions |

## Data Model Changes

```python
# New dataclasses (see design.md for full definitions)
Session
ContextEnhancedQuery
ModeDecision
DigestedInformation
WorkerConfig
Task (tree node)
TaskResult
ContextUpdate
ReviewerDecision
AcceptedResult
WorkerResult
AgentState
ExecutionLog
ExecutionLogEntry
```

## API Changes

None — library-only changes with no external API endpoints.

## Dependencies

### External Dependencies

None — standard library only.

### Internal Dependencies

- [x] No blocking dependencies; changes are self-contained within `src/tinycua`.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Schema drift between docs and implementation | High | Derive all fields from canonical `state-objects.md` and update docs in this PR |
| Serialization edge cases with deep nesting | Medium | Add nested Task tree serialization round-trip test with multi-level child_tasks |
| Missing fields in `from_dict()` | Medium | Unit tests that cover round-trip for every type |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-30*
