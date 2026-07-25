# ReviewerDecision

> **Package:** `tinycua.models.reviewer_decision`
> **Status:** Target architecture

## Role

Reviewer decision models capture `TinyCUAResultReviewerNode` output.

```text
ReviewerDecision
  · outcome: Literal["approved", "needs_revision", "rejected", "replan"]
  · rationale: str
  · target_task_id: str | None
  · metadata: dict
```

## ReviewerDecision Responsibilities

- Record a concise free-form review report
- Decide approved / needs_revision / rejected / replan
- Update active `TaskResult`
- Optionally hand useful claims to future task context
- Trigger task-tree transition

> **Vocabulary (FR-057):** `rejected` is aliased to `needs_revision` — both send the
> task back for revision with the same loop behavior. `open_question` is off by
> default; it is only available when explicitly enabled via reviewer config.

## Replan Path

When `ResultReviewer` returns `replan`:

```text
ResultReviewer decision = replan
  → spawn/prepend TaskAssessor(scope=active_task_or_local_region)
  → TaskAnalyzer(mode=local_replan, init_enabled=false)
  → TaskExecutor
```

Replan is a local execution-time recovery path. It MUST NOT spawn
`AnalysisEffortNode` and MUST NOT run the Worker-owned effort-gated upfront
TaskAnalysisLoop. See [`../loops/node.md`](../loops/node.md) for the full flow.

## Open Question Behavior

`open_question` means no terminal decision yet. It keeps the relevant node active for
continuation rather than forcing a terminal result.

When `ResultReviewer` returns `open_question`:
- Keep or requeue the `ResultReviewer` as the active continuation target.
- Install `mandatory_passthrough` targeting that `ResultReviewer` node/session.
- Route the next user input directly to it unless the user explicitly restarts progress.

This ensures the next message deterministically reaches the same reviewer/session that
requested the open question.

## Related

- [`../loops/node.md`](../loops/node.md)
- [`../loops/worker_concept.md`](../loops/worker_concept.md)
- [`../loops/route_map.md`](../loops/route_map.md)
