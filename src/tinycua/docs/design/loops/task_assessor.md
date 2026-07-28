# TinyCUATaskAssessorNode

> **Package:** `tinycua.loops.task_assessor`
> **Status:** Target architecture

## Role

`TinyCUATaskAssessorNode` is a concrete, read-only planning reviewer. It treats tasks as
recursively refinable outcomes rather than required atomic steps. Current granularity is
adequate when a task's outcome and boundaries support a focused execution attempt and
meaningful review from observable evidence. Further decomposition is warranted only when
separating responsibilities, dependencies, uncertainty, or evidence materially improves
execution or review.

The assessor evaluates children as scoped contributions and parents as integrated
outcomes. It selects only material defects, reports a shared defect on its narrowest
useful node, and preserves explicit workflows and hard constraints. Size, possible finer
decomposition, executor-local choices, and analysis effort alone are not defects. The
assessor never imposes architecture, task counts, decomposition depth, command-level
work, or unsupported implementation choices.

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

- Evaluates only the current active task and nearby local region.
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
