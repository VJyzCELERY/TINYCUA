# Design Document: State Objects (M1)

**Spec**: ./spec.md
**Status**: Complete
**Last Updated**: 2026-05-30

---

## Overview

Implement all TINYCUA shared state objects as Python dataclasses under a new `tinycua.state` module. Each state object mirrors the canonical YAML schema from `src/tinycua/docs/architecture/state-objects.md` and provides `to_dict()` / `from_dict()` / `to_json()` / `from_json()` serialization. No external framework dependencies beyond the Python standard library.

---

## Architecture

### Module Layout

```
src/tinycua/tinycua/
├── __init__.py
├── agent/
├── cli/
└── state/                          # NEW
    ├── __init__.py                 # Re-exports all public types
    ├── session.py                  # Session
    ├── mode_decision.py            # ContextEnhancedQuery, ModeDecision
    ├── digested_information.py     # DigestedInformation
    ├── worker_config.py            # WorkerConfig
    ├── task.py                     # Task, TaskList
    ├── task_result.py              # TaskResult
    ├── reviewer.py                 # ReviewerDecision
    ├── worker_result.py            # WorkerResult
    ├── agent_state.py              # AgentState
    ├── execution_log.py            # ExecutionLog, ExecutionLogEntry
    └── base.py                     # Shared base class with serialize helpers
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/state/` | New | Entire new module — 11 source files + `__init__.py` + `base.py` |
| `tinycua/__init__.py` | Modified | May optionally re-export `tinycua.state` submodule |
| `docs/architecture/state-objects.md` | Modified | Update AgentState status values and descriptions |
| `docs/architecture/session-architecture.md` | Modified | Update Session owner_type values and descriptions |

---

## Data Model

### Base Serialization Protocol

All state objects inherit from a `StateObject` base class that provides:

```python
class StateObject:
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> Self: ...
    def to_json(self, **json_kwargs) -> str: ...
    @classmethod
    def from_json(cls, json_str: str) -> Self: ...

    @staticmethod
    def _validate_enum(value: str, allowed: set[str], field_name: str) -> None:
        """Validate that *value* is one of the *allowed* values for *field_name*.
        Raises ValueError with a consistent message on failure."""
        ...
```

Implementation uses `dataclasses.dataclass` + `dataclasses.asdict()` for `to_dict()`, and per-field construction in `from_dict()`. JSON methods delegate to `json.dumps` / `json.loads`.

#### Nested Deserialization Strategy

`to_dict()` uses `dataclasses.asdict()` which handles recursive serialization of nested custom-typed fields transparently. For `from_dict()`, the base `StateObject` uses `typing.get_type_hints()` + `dataclasses.fields()` introspection to auto-convert nested custom types from raw dicts back into their typed objects:

- The base `from_dict()` inspects each field's type annotation via `typing.get_type_hints(cls)`.
- If a field's annotation is itself a `@dataclass` subclass of `StateObject`, `from_dict()` is called recursively to reconstruct it.
- For `list[T]` where `T` is a `StateObject` subclass, each element is recursively deserialized.
- For `list[T]` where `T` is a standard Python type (e.g., `str`, `float`), elements are left as-is.
- For `T | None` (Optional), the value is converted if non-None, else kept as None.

This approach means subclasses do NOT need to override `from_dict()` — the base class handles all nested deserialization automatically. The `to_dict()`/`from_dict()` contract provides **structural typing**: any dict produced by `to_dict()` round-trips through `from_dict()` to reconstruct the original typed object tree.

All enum-typed fields are validated in `__post_init__` via a shared `_validate_enum` helper from the `StateObject` base class (see Technical Decision #5). Only `ModeDecision` cross-field validation is shown explicitly below as it involves multiple fields.

### Enum Types

```
ModeType = Literal["primary_agent", "worker", "uncertain"]
UncertainNextAction = Literal["ask_user", "explore"] | None
EffortLevel = Literal["none", "high"]
TaskStatus = Literal["completed", "failed", "blocked"]
ReviewStatus = Literal["accepted", "retry", "replan", "escalate_user"]
AgentStatus = Literal["idle", "running", "blocked", "terminated"]
OwnerType = Literal["primary", "child"]
```

### Core State Objects

```python
@dataclass
class Session:
    session_id: str
    owner_type: OwnerType             # primary | child
    owner_name: str
    chat_history: list[dict]          # JSON turn log entries
    context: str                      # Structured markdown
    execution_log: ExecutionLog | None = None

@dataclass
class ContextEnhancedQuery:
    enhanced_query: str

@dataclass
class ModeDecision:
    mode: ModeType
    score: float
    confidence: float
    reasons: list[str]
    uncertain_next_action: UncertainNextAction = None  # "ask_user" | "explore"

    def __post_init__(self):
        if self.mode == "uncertain" and self.uncertain_next_action is None:
            raise ValueError(
                "uncertain_next_action is required when mode is 'uncertain'"
            )

@dataclass
class DigestedInformation:
    context_summary: str
    key_points: list[str]
    advisory_instructions: str | None = None
    constraints: list[str] | None = None
    known_gaps: list[str] | None = None

@dataclass
class WorkerConfig:
    effort: EffortLevel

@dataclass
class Task:
    task_id: str
    name: str
    description: str
    context: str
    success_criteria: list[str]
    confidence: float                 # 0.0–1.0 (implementation calibration)
    tasks: list[Task] | None = None  # If present, this is a container task

@dataclass
class TaskList:
    tasks: list[Task]
    current_task_id: str | None = None

@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    result: str
    discovered_sequence_issues: list[str] | None = None
    uncertainty_notes: list[str] | None = None

@dataclass
class ContextUpdate:
    target_task_id: str
    update: str

@dataclass
class ReviewerDecision:
    task_id: str
    status: ReviewStatus
    reason: str
    confidence: float
    context_updates: list[ContextUpdate] | None = None
    retry_instructions: str | None = None

@dataclass
class AcceptedResult:
    task_id: str
    name: str
    result: str

@dataclass
class WorkerResult:
    accepted_results: list[AcceptedResult]

@dataclass
class AgentState:
    active_agent: str
    active_task_id: str | None = None
    status: AgentStatus = "idle"
    resume_target: str | None = None
    consecutive_failures: int = 0

@dataclass
class ExecutionLogEntry:
    action: str
    outcome: str
    decision: str | None = None

@dataclass
class ExecutionLog:
    entries: list[ExecutionLogEntry]
```

### Schema Changes

Architecture doc schema values updated for AgentState status and Session owner_type (see Implementation Phases).

---

## API / Interface Contracts

### Public API: `tinycua.state` package

```python
from tinycua.state import (
    Session,
    ContextEnhancedQuery,
    ModeDecision,
    DigestedInformation,
    WorkerConfig,
    Task,
    TaskList,
    TaskResult,
    ReviewerDecision,
    WorkerResult,
    AgentState,
    ExecutionLog,
    ExecutionLogEntry,
    ContextUpdate,
    AcceptedResult,
    # Enum-style type aliases
    ModeType,
    TaskStatus,
    ReviewStatus,
    AgentStatus,
    EffortLevel,
    OwnerType,
    UncertainNextAction,
)
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Invalid enum value in field | `ValueError("Invalid value '...' for field 'mode': expected one of ...")` | Raised during `__post_init__` validation |
| Negative `consecutive_failures` | `ValueError("consecutive_failures must be non-negative")` | |
| Missing required field in `from_dict()` | `ValueError` | `from_dict` pre-validates all required keys are present, raises `ValueError` with the missing field name before construction |
| Invalid JSON in `from_json()` | `json.JSONDecodeError` | Propagated from stdlib |
| Type mismatch in `from_dict()` | `TypeError` or `ValueError` | Incompatible type for field |

---

## Implementation Phases

### Phase 1 — MVP

- [ ] Update `docs/architecture/state-objects.md` — AgentState status values and descriptions
- [ ] Update `docs/architecture/session-architecture.md` — Session owner_type values and descriptions
- [ ] Write serialization round-trip tests (TDD — expect RED)
- [ ] Write unit test stubs for all state object types
- [ ] Create `tinycua/state/base.py` with `StateObject` base class
- [ ] Create all state object modules (session, mode_decision, digested_information, worker_config, task, task_result, reviewer, worker_result, agent_state, execution_log)
- [ ] Create `tinycua/state/__init__.py` re-exporting all public types
- [ ] Implement serialization and validation (TDD — iterate until GREEN)
- [ ] Complete unit tests with full coverage
- [ ] Run `uv run pytest` with full coverage

### Phase 2 — Enhancements

None — Phase 1 covers the full M1 scope.

---

## Technical Decisions

**Compatibility**: This module requires Python 3.11+ due to `Self` return type (PEP 673) and `|` union syntax (PEP 604). Backward compatibility with Python 3.10 can be achieved with `from __future__ import annotations` and `typing_extensions.Self` if needed; this is documented here as a known tradeoff.

1. **Decision**: Use `dataclasses.dataclass` rather than `pydantic.BaseModel` or `attrs`.
   - **Reason**: Zero external dependencies. Python stdlib only. TINYCUA's state objects are simple data containers, not complex validated models.
   - **Alternatives Considered**: Pydantic — rejected for introducing a dependency for simple serialization. attrs — unnecessary when dataclasses suffice. NamedTuple — rejected because mutable fields and inheritance are needed.

2. **Decision**: Custom `StateObject` base class with `to_dict()` / `from_dict()` rather than third-party serialization library.
   - **Reason**: Keeps the interface uniform across all types. `dataclasses.asdict()` handles most of `to_dict()`. `from_dict()` is straightforward field-by-field construction.
   - **Alternatives Considered**: `marshmallow` — overkill for flat/one-level-nested objects. Manual `__iter__` — less explicit.

3. **Decision**: Separate file per logical group (session.py, task.py, etc.) rather than one massive `state.py`.
   - **Reason**: Readability, maintainability, diff clarity. Related types co-located (e.g., `Task` and `TaskList` together).
   - **Alternatives Considered**: Single `state.py` — rejected because it would be ~500+ lines.

4. **Decision**: Enum-typed string literals rather than `enum.Enum` subclasses.
   - **Reason**: Simpler serialization — no extra conversion step needed for JSON. Type aliases provide IDE support.
   - **Alternatives Considered**: `enum.Enum` — would require additional conversion in `to_dict()` since `dataclasses.asdict()` preserves enum objects rather than string values. Rejected for added complexity with no benefit for simple string-constrained fields.

5. **Decision**: Per-class `__post_init__` with shared `_validate_enum` helper in `StateObject` base class for enum field validation.
   - **Reason**: Ensures consistent error messages and validation behavior across all state objects. The shared `_validate_enum(value, allowed_set, field_name)` method produces uniform `ValueError("Invalid value '...' for field '...': expected one of ...")` messages. Cross-field validation rules (e.g., ModeDecision's uncertain_next_action requirement) are handled in per-class `__post_init__` methods.
   - **Alternatives Considered**: Per-class manual checks without shared helper — rejected for producing inconsistent error message formats. Enum subclass validation — rejected because `Literal` string aliases are already chosen over `enum.Enum` (Decision #4).

6. **Decision**: `ContextEnhancedQuery` is a single-field dataclass rather than a bare `str` or type alias.
   - **Reason**: The dataclass wrapper provides a stable type identity that distinguishes enriched queries from raw query strings in the type system and supports future extension with provenance/metadata fields (e.g., enrichment timestamp, source context references) without breaking consumers.
   - **Alternatives Considered**: Bare `str` — provides no type safety distinction from raw queries. `TypeAlias` — same issue, no structural distinction at runtime.

---

## Architecture Doc Updates (In Scope)

The following changes to `docs/architecture/` are applied in this PR to align canonical schemas before implementation:

| Doc | Change |
|-----|--------|
| `state-objects.md` — AgentState status | `running \| waiting_for_user \| terminated` → `idle \| running \| blocked \| terminated` |
| `session-architecture.md` — Session owner_type | `primary \| tinycua_internal \| future_sub_agent` → `primary \| child` |
| `session-architecture.md` — owner_type description | Update to reflect `primary` (user-facing root) and `child` (sub-session) model with parent/child chat history propagation and context isolation rules |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Schema drift between architecture docs and implementation | Medium | High | All field names and types derived directly from canonical `state-objects.md`. Derivation review in PR. |
| Serialization edge cases with deep nesting | Low | Medium | Test with 5+ levels of nested Task containers |
| Missing fields in `from_dict()` after schema updates | Low | Medium | Unit tests that verify round-trip for every type catch this immediately |
| Conflicts with existing `tinycua/agent/` module | Low | Low | `state/` is a new orthogonal module, no overlap |

---

## Resolved Questions

The following questions from the spec and earlier design drafts have been resolved through review:

1. **Validation strictness** — `ModeDecision(mode="worker", uncertain_next_action="explore")` is allowed (consumers should ignore `uncertain_next_action` when mode is not `"uncertain"`). When mode is `"uncertain"`, `uncertain_next_action` is required and validated in `__post_init__` (cross-field validation), matching the canonical constraint in `state-objects.md`.
2. **ExecutionLogEntry** — Confirmed as a separate public dataclass (not an inline dict).
3. **ContextUpdate** — Confirmed as a separate public dataclass with `target_task_id` and `update` fields.
4. **Session.execution_log** — Typed as `ExecutionLog | None` (not a raw list). Defaulting to `None` because a session may not have spawned sub-sessions yet when first created. An empty `ExecutionLog` (entries=[]) could alternatively be the default; choosing `None` to distinguish "no log yet" from "empty log."
5. **OwnerType values** — Changed to `Literal["primary", "child"]` to avoid the ambiguous `future_sub_agent` term. The `child` value is intentionally broad for MVP and covers both internal specialized-agent sub-sessions and future standalone sub-agent sessions. The distinction between them, if needed, will be handled by other fields or in a future milestone.
6. **AgentState status** — Values changed to `idle`, `running`, `blocked`, `terminated` with default `"idle"`.
7. **Literal vs enum.Enum** — Confirmed use of `Literal` string aliases with manual `__post_init__` validation.
8. **chat_history** — Kept as `list[dict]` for MVP simplicity; a dedicated `ChatHistoryEntry` type may be added later. The arch doc's YAML `"<JSON turn log entries>"` is a documentation placeholder representing a JSON-serializable array; the Python representation is `list[dict]`.

---

## References

- Spec: `./spec.md`
- Architecture state objects: `src/tinycua/docs/architecture/state-objects.md`
- Architecture overview: `src/tinycua/docs/architecture/overview.md`
