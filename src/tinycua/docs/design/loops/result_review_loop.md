# ResultReviewLoop

> **File:** `docs/design/loops/result_review_loop.md`
> **Last Updated:** 2026-06-01

---

## Role

Reviews task execution results and writes `ResultReviewerState` when an actionable
decision exists.

Classification labels:

```text
["accept", "retry", "replan"]
```

`escalate_user` is removed. If the reviewer cannot decide, the loop keeps the reviewer
active with an open question and does not write a terminal decision.

```text
session.agent_state = ResultReviewerState(
  type="result_reviewer",
  status="terminated" | "running",
  decision="accept" | "retry" | "replan" | None,
  reason=...,
  context_updates=[...],
)
```

---

## Related

- [ResultReviewer AgentNode](../agent_sessions/result_reviewer.md)
- [ResultReviewerState](../state/information.md#resultreviewerstate)
