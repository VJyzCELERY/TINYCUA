# WorkerResult

> **Package:** `tinycua.models.worker_result`
> **Status:** Target architecture

## Role

Worker result models capture `TinyCUAWorkerNode` decisions and restart/recreation
signals.

```text
WorkerResult
  · label: Literal["task_recreation", "task_reanalysis", "passthrough", "proceed_execution"]
  · confidence: float | None
  · rationale: str | None
  · target_node_id: str | None
  · restart_requested: bool = false
  · recreate_task: bool = false
  · metadata: dict
```

`TinyCUAWorkerNode` replaces the old worker subgraph. It performs deterministic checks
and optional LLM decision without spawning a worker QueryAnalyst node.

## Related

- [`../loops/worker_concept.md`](../loops/worker_concept.md)
- [`classification.md`](classification.md)
