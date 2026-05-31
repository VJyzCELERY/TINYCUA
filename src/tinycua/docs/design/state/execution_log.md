# Execution Log

> **File:** `docs/design/state/execution_log.md`
> **Package:** `tinycua.state.execution_log`
> **Last Updated:** 2026-05-31

---

## Role

`ExecutionLog` records actions and outcomes from sub-session execution for auditability.
Stored in the existing `Session.execution_log` field.

---

## Class Contract

**File:** `tinycua/state/execution_log.py`

```python
@dataclass
class ExecutionLogEntry(StateObject):
    action: str                 # action that was taken
    outcome: str                # outcome of the action
    decision: str | None = None # optional decision trace/reasoning

@dataclass
class ExecutionLog(StateObject):
    entries: list[ExecutionLogEntry]
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Flat list of entries | `ExecutionLog` wraps `list[ExecutionLogEntry]` | Simple append-only audit trail |
| Decision trace optional | `decision: str | None` | Not every action needs a decision annotation |


---


---


---

## See also

Prev : [`WorkerResult` + `WorkerConfig`](worker_result.md) | Next : [Design `Session`](session.md)
