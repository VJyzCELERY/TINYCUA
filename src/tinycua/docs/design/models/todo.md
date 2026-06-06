# Todo

> **Package:** `tinycua.models.todo`
> **Status:** Target architecture

## Role

`Todo` is the per-session linear plan-then-execute list available to every node session.
It is distinct from `Task`, which is the root session's overall goal.

`Todo` is intentionally small and flat:

- no nested subtodos
- no dependency graph
- no priorities
- default maximum of 20 items
- one ordered list per session

## Contract

```text
Todo
  · items: list[TodoItem]
  · max_items: int = 20
  · append(description: str) → None
  · mark_done(index: int) → None
  · next_pending() → TodoItem | None

TodoItem
  · description: str
  · status: Literal["pending", "done"]
  · order: int
  · metadata: dict
```

Nodes may read, append, and mark items done while executing. A node is not required to
use Todo, but its session provides access to one so the node can plan then execute in a
simple, checkable sequence.

## Related

- [`session.md`](session.md)
- [`task.md`](task.md)
- [`../tools/todo.md`](../tools/todo.md)
