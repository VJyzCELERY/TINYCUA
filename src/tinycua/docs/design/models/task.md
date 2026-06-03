# Task

> **Package:** `tinycua.models.task`
> **Status:** Target architecture

## Role

Task models represent worker task trees, active tasks, task results, and task sharing.

Task sharing remains explicit. Child/per-node sessions do not automatically inherit a
task unless TinyCUA assigns or scopes it.

Task replacement propagation follows session/task sharing rules and should not cross
configured boundaries.

## Related

- [`session.md`](session.md)
- [`../tools/task.md`](../tools/task.md)
- [`../loops/worker_concept.md`](../loops/worker_concept.md)
