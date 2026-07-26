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

- A validated `task_assessment_decision` handoff with a non-empty rationale.
- `ready` requires an empty selection and skips only the paired analyzer.
- `analyze` requires one or more valid unfinished references, canonicalized and deduplicated for TaskAnalyzer.

## Tools

| Tool Scope | Description |
|------------|-------------|
| `task_inspect` | Read task state without mutating it. |
| `task_assessment_decision` | Validate and hand off `ready` or `analyze`. |

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
TaskAssessor commits task_assessment_decision:
  → analyze with valid unfinished tasks:
      advance queue; next is TaskAnalyzerNode
  → ready with an empty selection:
      remove only the paired TaskAnalyzerNode; advance to the following node
```

Missing or terminal task references, blank rationale, and mismatched decision/selection
shapes are rejected. The assessor remains read-only.

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
