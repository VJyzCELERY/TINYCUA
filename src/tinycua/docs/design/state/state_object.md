# StateObject

> **File:** `docs/design/state/state_object.md`
> **Package:** `tinycua.state.base`
> **Last Updated:** 2026-05-31

---

## Role

`StateObject` is the base class for all TINYCUA state objects. Every state class
(Task, Session, ModeDecision, etc.) extends it and inherits JSON/dict round-trip
serialization via `dataclasses.asdict()` plus automatic nested deserialization.

Not a dataclass itself — subclasses must be `@dataclass`-decorated.

---

## Class Contract

**File:** `tinycua/state/base.py`

```python
class StateObject:
    """Base class providing serialization for all state object dataclasses."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-serializable dict via dataclasses.asdict()."""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Deserialize with automatic nested StateObject conversion.

        Uses typing.get_type_hints() to resolve field types. Handles:
        - Nested StateObject subclasses (auto-deserialized recursively)
        - Optional[T] (strips None from Union)
        - list[T] (deserializes each element)
        - dict (passed through as-is)
        - Missing fields: uses defaults, raises ValueError if required.
        """

    def to_json(self, **json_kwargs) -> str:
        """Serialize to JSON string via json.dumps(self.to_dict())."""

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Deserialize from JSON string via json.loads + from_dict()."""

    @staticmethod
    def _validate_enum(value: str, allowed: set[str], field_name: str) -> None:
        """Raise ValueError if value is not in allowed set."""
```

---

## Nested Deserialization

`from_dict()` handles recursive state objects automatically. Example:

```python
# Task has child_tasks: list[Task] | None and task_result: TaskResult | None
data = {"task_id": "T-0", "child_tasks": [{"task_id": "T-0.1", ...}], ...}
task = Task.from_dict(data)
# child_tasks[0] is a Task instance, task_result is None
# Parent references auto-re-established via Task.set_parents()
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Not a dataclass | Plain class with explicit serialization | Subclasses are dataclasses; base provides methods only |
| `from_dict()` uses type hints | `typing.get_type_hints()` | Auto-resolves Optional, list[T], nested StateObject without manual mapping |
| `to_dict()` delegates to stdlib | `dataclasses.asdict()` | Standard, well-tested, recursive |
| Enum validation helper | `_validate_enum()` | Consistent error messages across all state classes |


---


---


---

## See also

Prev : [`MainLoop` Orchestration](../loops/main_loop.md) | Next : [Per-Agent State Classes](information.md)
