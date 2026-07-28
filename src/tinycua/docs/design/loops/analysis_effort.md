# TinyCUAAnalysisEffortNode

> **Package:** `tinycua.loops.analysis_effort`
> **Status:** Target architecture

## Role

`TinyCUAAnalysisEffortNode` is a concrete `ProcessNode` that controls how many upfront
task-granularity reassessment opportunities occur before execution. Each opportunity
runs TaskAssessor and retains the paired TaskAnalyzer only when material defects are
selected. It is owned by the Worker and runs deterministically — no LLM call is required.

## WorkerEffort

```text
WorkerEffort = none | low | medium | high
```

Mapping to pass limits:

| Effort | Pass Limit | Description |
|--------|------------|-------------|
| `none` | 0 | Skip analyzer-eligible reassessment passes |
| `low` | 1 | One extra assessment opportunity |
| `medium` | 2 | Two extra assessment opportunities |
| `high` | 3 | Three extra assessment opportunities |

`none` means "skip analyzer-eligible reassessment passes and continue to final assessment
and execution" — it does NOT terminate the Worker.

## Behavior

```text
AnalysisEffortNode(pass_count=0, pass_limit=effort_to_pass_limit(config.effort))
  while pass_count < pass_limit:
      prepend [TaskAssessor, TaskAnalyzer] to the queue
      pass_count += 1
  when threshold reached:
      prepend TaskAssessor(final_assessment)
      then advance to TaskExecutor
```

`AnalysisEffortNode` tracks `pass_count` and prepends `[TinyCUATaskAssessorNode,
TinyCUATaskAnalyzerNode]` until the configured threshold is reached. A `ready` assessor
decision removes its paired analyzer, so effort never requires mutation, decomposition,
a fixed depth, or a task count. When the threshold is reached, `AnalysisEffortNode` MUST
spawn a final assessment before TaskExecutor. That final assessor records any remaining
findings as exhausted advisories and proceeds without another analyzer, so the queue
cannot accidentally drain without execution.

## Queue Shape for Worker Planning Paths

```text
[TaskCreate or TaskAnalyzer, AnalysisEffortNode, FinalAssessor, TaskExecutor, ResultReviewer, ResponseNode]
```

After the initial `TaskCreate` or `TaskAnalyzer` pass, `AnalysisEffortNode` controls how
many additional granularity assessments precede execution. Adequate tasks remain at their
current resolution; later execution or review may still trigger local decomposition.

## Config

```text
TinyCUAAnalysisEffortNodeConfig
  · effort: WorkerEffort = "none"
```

## Related

- [`worker_concept.md`](worker_concept.md)
- [`node.md`](node.md)
- [`../config/node_config.md`](../config/node_config.md)
