# Reviewer Decision

> **File:** `docs/design/state/reviewer_decision.md`
> **Package:** `tinycua.state.reviewer`
> **Last Updated:** 2026-06-01

---

## Role

`ReviewerDecision` is produced by the Result Reviewer — judgment on a task result
with optional targeted context updates and retry instructions.

> **Note:** This dataclass exists for typed internal use. The canonical output of
> ResultReviewer is `ResultReviewerState` (an AgentState subclass) which is written
> to `session.agent_state` and serialized via `to_yaml()`.

---

## Class Contract

**File:** `tinycua/state/reviewer.py`

```text
ContextUpdate extends StateObject
    · target_task_id: str — ID of task to update
    · update: str — context update string

ReviewerDecision extends StateObject
    · task_id: str — ID of reviewed task
    · status: ReviewStatus — accept | retry | replan
    · reason: str — reason for decision
    · confidence: float — confidence in decision
    · context_updates: list[ContextUpdate] | None = None
    · retry_instructions: str | None = None
```

`ReviewStatus = Literal["accept", "retry", "replan"]`

### Removed: `escalate_user`

`escalate_user` has been removed from `ReviewStatus`. When the ResultReviewer cannot
resolve, it does **not** call the classification tool. The loop does not write a
terminal result, leaving the agent active with an open question. The next user query
passthrough routes back to the same ResultReviewer, enabling human-in-the-loop
without a dedicated escalation mode.

If HITL is disabled via config, the agent keeps exploring (retry with exploration
tools). If HITL is enabled, the agent enters idle state, waiting for the next user
query to passthrough.

---

## Status Semantics

| Status | Meaning | Effect |
|--------|---------|--------|
| `accept` | Task result is valid | Context updates applied to unfinished tasks |
| `retry` | Recoverable issue | Task status → `not_started`; `retry_instructions` + context appended; TaskExecutor re-invoked |
| `replan` | Decomposition insufficient | Triggers TaskAssessor → TaskAnalyzer replan cycle; active task may change |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Targeted context updates | `list[ContextUpdate]` with `target_task_id` | Only specific tasks updated, not a full dump |
| Retry with instructions | `retry_instructions` field | Executor gets guidance on what to fix |
| No escalate_user | Agent stays active on indecision | HITL via passthrough; no special mode needed |
| Three decisions | `accept`, `retry`, `replan` | Covers all actionable outcomes; uncertainty = no decision |

---

## See also

Prev : [`DigestedInformation`](digested_information.md) | Next : [`WorkerResult` + `WorkerConfig`](worker_result.md)

## Related

- [Produced by ResultReviewer](../agent_sessions/result_reviewer.md)
- [Stored in ResultReviewerState](information.md)
- [Replan triggers TaskAssessor → TaskAnalyzer](../orchestration/worker.md)
