# Reviewer Decision

> **File:** `docs/design/state/reviewer_decision.md`
> **Package:** `tinycua.state.reviewer`
> **Last Updated:** 2026-05-31

---

## Role

`ReviewerDecision` is produced by the Result Reviewer — judgment on a task result
with optional targeted context updates and retry instructions.

---

## Class Contract

**File:** `tinycua/state/reviewer.py`

```python
@dataclass
class ContextUpdate(StateObject):
    target_task_id: str    # ID of task to update
    update: str            # context update string

@dataclass
class ReviewerDecision(StateObject):
    task_id: str                                     # ID of reviewed task
    status: ReviewStatus                             # accepted | retry | replan | escalate_user
    reason: str                                      # reason for decision
    confidence: float                                # confidence in decision
    context_updates: list[ContextUpdate] | None = None
    retry_instructions: str | None = None
```

`ReviewStatus = Literal["accepted", "retry", "replan", "escalate_user"]`

---

## Status Semantics

| Status | Meaning | Effect |
|--------|---------|--------|
| `accepted` | Task result is valid | Context updates applied to unfinished tasks |
| `retry` | Recoverable issue | `retry_instructions` sent back to executor |
| `replan` | Decomposition insufficient | Triggers roadmap revision |
| `escalate_user` | Cannot resolve | User-facing explanation |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Targeted context updates | `list[ContextUpdate]` with `target_task_id` | Only specific tasks updated, not a full dump |
| Retry with instructions | `retry_instructions` field | Executor gets guidance on what to fix |


---


---

## See also

Prev : [`DigestedInformation`](digested_information.md) | Next : [`WorkerResult` + `WorkerConfig`](worker_result.md)
