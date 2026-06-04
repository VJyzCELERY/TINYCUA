# ReviewerDecision

> **Package:** `tinycua.models.reviewer_decision`
> **Status:** Target architecture

## Role

Reviewer decision models capture `TinyCUAResultReviewerNode` output.

```text
ReviewerDecision
  · outcome: Literal["accept", "retry", "replan", "open_question"]
  · rationale: str | None
  · target_task_id: str | None
  · metadata: dict
```

`open_question` means no terminal decision yet.

Open question behavior keeps the relevant node active for continuation rather than
forcing a terminal result.

## Related

- [`../loops/node.md`](../loops/node.md)
- [`../loops/worker_concept.md`](../loops/worker_concept.md)
