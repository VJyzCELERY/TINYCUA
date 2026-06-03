# WorkerResult

> **Package:** `tinycua.models.worker_result`
> **Status:** Target architecture

## Role

Worker result models capture `TinyCUAWorkerNode` decisions and restart/recreation
signals.

`TinyCUAWorkerNode` replaces the old worker subgraph. It performs deterministic checks
and optional LLM decision without spawning a worker QueryAnalyst node.

## Related

- [`../loops/worker_concept.md`](../loops/worker_concept.md)
- [`classification.md`](classification.md)
