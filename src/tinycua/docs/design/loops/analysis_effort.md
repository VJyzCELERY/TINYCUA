# TinyCUAAnalysisEffortNode

> **Package:** `tinycua.loops.analysis_effort`
> **Status:** Target architecture

## Role

`TinyCUAAnalysisEffortNode` is a concrete `ProcessNode` that controls how many
upfront task-assessment and task-analysis passes occur before advancing to execution.
It is owned by the Worker and runs deterministically — no LLM call is required.

## WorkerEffort

```text
WorkerEffort = none | low | medium | high
```

Mapping to pass limits:

| Effort | Pass Limit | Description |
|--------|------------|-------------|
| `none` | 0 | Skip extra analysis passes; advance directly to executor |
| `low` | 1 | One extra `[TaskAssessor, TaskAnalyzer]` pass |
| `medium` | 2 | Two extra `[TaskAssessor, TaskAnalyzer]` passes |
| `high` | 3 | Three extra `[TaskAssessor, TaskAnalyzer]` passes |

`none` means "skip extra analysis passes and continue to executor" — it does NOT
terminate the Worker.

## Behavior

```text
AnalysisEffortNode(pass_count=0, pass_limit=effort_to_pass_limit(config.effort))
  while pass_count < pass_limit:
      prepend [TaskAssessor, TaskAnalyzer] to the queue
      pass_count += 1
  when threshold reached:
      advance to TaskExecutor
```

`AnalysisEffortNode` tracks `pass_count` and prepends `[TinyCUATaskAssessorNode,
TinyCUATaskAnalyzerNode]` until the configured threshold is reached. When the
threshold is reached, `AnalysisEffortNode` advances and allows `TaskExecutor` to run.

## Queue Shape for Worker Planning Paths

```text
[TaskCreate or TaskAnalyzer, AnalysisEffortNode, TaskExecutor, ResultReviewer, ResponseNode]
```

After the initial `TaskCreate` or `TaskAnalyzer` pass, `AnalysisEffortNode` controls
how many additional `[TaskAssessor, TaskAnalyzer]` rounds precede execution.

## Config

```text
TinyCUAAnalysisEffortNodeConfig
  · effort: WorkerEffort = "none"
```

## Related

- [`worker_concept.md`](worker_concept.md)
- [`node.md`](node.md)
- [`../config/node_config.md`](../config/node_config.md)
