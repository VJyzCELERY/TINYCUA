# Classification

> **Package:** `tinycua.models.classification`
> **Status:** Target architecture

## Role

Classification is produced by `TinyCUAQueryAnalystNode` at the top-level entrypoint and
by `TinyCUAWorkerNode` for worker-specific decisions.

There is no separate worker QueryAnalyst node.

Top-level labels:

```text
passthrough | worker | uncertain
```

- `passthrough`: forward user input to an already active or queued node/session.
- `worker`: route to TinyCUAWorkerNode for task planning/execution.
- `uncertain`: QueryAnalyst remains active and waits for user continuation.

Worker labels are dynamic:

```text
task_creation | task_recreation | task_reanalysis | passthrough | proceed_execution
```

- `task_creation`: deterministic first-time creation when no task exists.
- `task_recreation`: rebuild/replace existing task tree.
- `task_reanalysis`: refine existing task tree without full replacement.
- `passthrough`: forward input to an already active or queued worker-owned node/session.
  Added only when a worker-spawned node exists to receive it.
- `proceed_execution`: edge case when task and active task exist but no executor is
  queued/active.

## Related

- [`../loops/route_map.md`](../loops/route_map.md)
- [`../loops/worker_concept.md`](../loops/worker_concept.md)
