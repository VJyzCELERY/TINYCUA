# RouteMap

> **Package:** `tinycua.loops.route_map`
> **Status:** Target architecture

## Role

`RouteMap` is a lightweight dispatch table owned by concrete `DecisionNode` classes. It
maps validated decision labels to named route handlers that mutate `NodeQueue`.

It replaces `RouterNode` without becoming a standalone orchestration layer.

```text
Route
  · label: str
  · handler: Callable[[NodeQueue, DecisionResult], None]

RouteMap
  · routes: dict[str, Route]
  · dispatch(label, queue, result)
```

## Examples

```text
TinyCUAQueryAnalystNode.route_map:
  passthrough → route_passthrough()
  worker      → route_worker()

TinyCUAWorkerNode.route_map:
  task_recreation   → route_task_recreation()
  task_reanalysis   → route_task_reanalysis()
  passthrough       → route_passthrough()
  proceed_execution → route_proceed_execution()
```

Route handlers are callables. By convention they are named methods on the concrete
`DecisionNode`, but standalone callables are valid when tests and ownership are clear.

## Related

- [`node.md`](node.md)
- [`worker_concept.md`](worker_concept.md)
