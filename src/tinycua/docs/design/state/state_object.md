# StateObject

> **File:** `docs/design/state/state_object.md`
> **Package:** `tinycua.state.base`
> **Last Updated:** 2026-05-31

---

## Role

`StateObject` is the base class for all TINYCUA state objects. Every state class
(Task, Session, AgentState subclasses, classification value objects, etc.) extends it and inherits JSON/dict round-trip
serialization via `dataclasses.asdict()` plus automatic nested deserialization.

Not a dataclass itself — subclasses must be `@dataclass`-decorated.

---

## Class Contract

**File:** `tinycua/state/base.py`

```text
StateObject — base class providing serialization for all state object dataclasses

    to_dict() → dict[str, Any]
        · Serialize to JSON-serializable dict via dataclasses.asdict()

    from_dict(data: dict[str, Any]) → Self (classmethod)
        · Deserialize with automatic nested StateObject conversion
        · Uses typing.get_type_hints() to resolve field types
        · Handles nested StateObject subclasses (auto-deserialized recursively)
        · Handles Optional[T] (strips None from Union)
        · Handles list[T] (deserializes each element)
        · Handles dict (passed through as-is)
        · Missing fields: uses defaults, raises ValueError if required

    to_json(**json_kwargs) → str
        · Serialize to JSON string via json.dumps(self.to_dict())

    from_json(json_str: str) → Self (classmethod)
        · Deserialize from JSON string via json.loads → from_dict()

    _validate_enum(value: str, allowed: set[str], field_name: str) → None (staticmethod)
        · Raise ValueError if value is not in allowed set
```

---

## Nested Deserialization

`from_dict()` handles recursive state objects automatically. Example:

```text
· Task has field child_tasks: list[Task] | None and task_result: TaskResult | None
· input data → {"task_id": "T-0", "child_tasks": [{"task_id": "T-0.1", ...}], ...}
· task → Task.from_dict(data)
· result: child_tasks[0] is a Task instance, task_result is None
· parent references auto-re-established via Task.set_parents()
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

Prev : [`AgentLoop` Overview](../loops/overview.md) | Next : [Per-Agent State Classes](information.md)


## Related

- [All per-agent state classes extend StateObject](information.md)
- [Session extends StateObject](session.md)
- [Task and TaskResult extend StateObject](task.md)
