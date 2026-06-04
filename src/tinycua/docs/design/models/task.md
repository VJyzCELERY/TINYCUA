# Task

> **Package:** `tinycua.models.task`
> **Status:** Target architecture

## Role

Task models represent worker task trees, active tasks, task results, and task sharing.

```text
Task
  · task_id: str
  · title: str
  · description: str
  · status: Literal["pending", "in_progress", "blocked", "done", "failed"]
  · children: list[Task]
  · active_child_id: str | None
  · result: TaskResult | None
  · metadata: dict

TaskResult
  · task_id: str
  · status: Literal["accepted", "retry", "replan", "open_question", "failed"]
  · summary: str
  · artifacts: list[dict]
  · metadata: dict
```

Task sharing remains explicit. Child/per-node sessions do not automatically inherit a
task unless TinyCUA assigns or scopes it.

Task replacement propagation follows session/task sharing rules and MUST NOT cross
configured boundaries.

## Related

- [`session.md`](session.md)
- [`../tools/task.md`](../tools/task.md)
- [`../loops/worker_concept.md`](../loops/worker_concept.md)
