# Classification

> **Package:** `tinycua.models.classification`
> **Status:** Target architecture

## Role

Classification is produced by `TinyCUAQueryAnalystNode` at the top-level entrypoint and
by `TinyCUAWorkerNode` for worker-specific decisions.

There is no separate worker QueryAnalyst node.

Top-level labels:

```text
passthrough | worker
```

Worker labels are dynamic:

```text
task_recreation | task_reanalysis | proceed_execution
```

`passthrough` is added only when a worker-spawned node exists to receive it.

## Related

- [`../loops/route_map.md`](../loops/route_map.md)
- [`../loops/worker_concept.md`](../loops/worker_concept.md)
