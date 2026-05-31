# Worker Result

> **File:** `docs/design/state/worker_result.md`
> **Package:** `tinycua.state.worker_result`, `tinycua.state.worker_config`
> **Last Updated:** 2026-05-31

---

## Role

`WorkerResult` aggregates accepted task results for Primary Agent consumption.
`WorkerConfig` controls worker effort level during task creation.

---

## Class Contract

**File:** `tinycua/state/worker_result.py`, `tinycua/state/worker_config.py`

```python
@dataclass
class AcceptedResult(StateObject):
    task_id: str       # ID of accepted task
    name: str          # name of accepted task
    result: str        # task output text

@dataclass
class WorkerResult(StateObject):
    accepted_results: list[AcceptedResult]

@dataclass
class WorkerConfig(StateObject):
    effort: EffortLevel  # "none" | "high"
```

**Type aliases:** `EffortLevel = Literal["none", "high"]`

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Accepted only | `accepted_results` | Only approved results reach Primary Agent |
| Separated from WorkerConfig | Two classes | Configuration and output are distinct concerns |


---


---

## See also

Prev : [`ReviewerDecision` + `ContextUpdate`](reviewer_decision.md) | Next : [`ExecutionLog` + `ExecutionLogEntry`](execution_log.md)
