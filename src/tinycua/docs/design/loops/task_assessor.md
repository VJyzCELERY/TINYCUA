# TinyCUATaskAssessorNode

> **Package:** `tinycua.loops.task_assessor`
> **Status:** Target architecture

## Role

`TinyCUATaskAssessorNode` is a concrete, read-only planning reviewer. It evaluates whether
every unfinished task is a coherent, actionable, and verifiable outcome. Once declared
dependencies are met, an actionable task supports focused execution without hidden
replanning or intentional sibling work; a verifiable task has specific observable
evidence from which a reviewer can decide completion. The assessor also checks that the
roadmap collectively covers explicit workflows and hard constraints. It selects every
task with a material planning defect and operates in two modes depending on the caller.

The assessor does not impose unsupported architecture, output layout, tool choice, a
fixed task count, command-level work, or decomposition depth. It splits materially
distinct outcomes while keeping tightly coupled work together.

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
