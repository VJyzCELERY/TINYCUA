# TinyCUATaskAssessorNode

> **Package:** `tinycua.loops.task_assessor`
> **Status:** Target architecture

## Role

`TinyCUATaskAssessorNode` is a concrete `ProcessNode` that evaluates the task tree and
selects unfinished tasks for decomposition or reanalysis. It operates in two modes
depending on the caller.

## Non-Responsibilities

- Does not decompose or analyze tasks (that belongs to TaskAnalyzer).
- Does not execute tasks (that belongs to TaskExecutor).
- Does not create new tasks (that belongs to TaskCreate or TaskAnalyzer in recreation
  mode).

## Inputs

- Current task tree state.
- Mode context (effort-loop or reviewer-replan).

## Outputs / State Produced

- List of selected unfinished tasks for TaskAnalyzer to process.
- If no tasks are selected, signals that no analyzer pass is needed.

## Tools

| Tool Scope | Description |
|------------|-------------|
| Task assessment / read / update tools | Assess task completeness and select unfinished tasks. |

## Modes

### Effort-Loop Mode

- Evaluates the full task tree.
- Selects only unfinished tasks.
- Accepted/finished tasks must not be selected.

### Reviewer-Replan Mode

- Evaluates the current active task / local region first, then consolidates with the
  rest of the tree.
- Selects only unfinished tasks.
- Accepted/finished tasks must not be selected.

## Queue Behavior / `on_complete()`

```text
TaskAssessor completes:
  → If tasks selected:
      advance queue; next is TaskAnalyzerNode
  → If no tasks selected (effort loop):
      do not spawn analyzer; advance back to AnalysisEffortNode
```

### Effort Loop Queue Examples

```text
When tasks selected:
  [EffortNode]
    → [Assessor, Analyzer, EffortNode]

When no tasks selected:
  [EffortNode]
    → [Assessor, EffortNode]
    → [EffortNode]
```

## Propagation

- Propagates selected task list for TaskAnalyzer consumption.

## Failure / Retry Behavior

Retry according to `NodeRetryPolicy`.

## Related Config

- `NodeToolPolicy` — assessment tool scope.
- `NodeRetryPolicy` — retry behavior.

## Related

- [`analysis_effort.md`](analysis_effort.md)
- [`task_analyzer.md`](task_analyzer.md)
- [`node.md`](node.md)
