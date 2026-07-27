# TinyCUATaskAnalyzerNode

> **Package:** `tinycua.loops.task_analyzer`
> **Status:** Target architecture

## Role

`TinyCUATaskAnalyzerNode` is a concrete `ProcessNode` that produces or refines an
actionable roadmap. It grounds planning decisions in available evidence and commits the
structural refinement required for its assigned region.

Every task represents one coherent, actionable, and verifiable outcome. Once declared
dependencies are met, an actionable task has enough objective, boundary, constraint,
and context information for focused execution without hidden replanning or intentional
sibling work. A verifiable task has specific observable evidence from which a reviewer
can decide completion. The roadmap collectively covers explicit workflows and hard
constraints. The analyzer makes evidence-supported decisions needed for execution,
avoids overlap and command-level or lifecycle-only tasks, keeps tightly coupled work
together, and never imposes a fixed task count.

## Non-Responsibilities

- Does not create root tasks (that belongs to TaskCreateNode).
- Does not execute tasks (that belongs to TaskExecutor).
- Does not issue the read-only readiness decision (that belongs to TaskAssessor).

## Inputs

- Previous query/continuation from upstream node.
- Mode-specific continuation prompt.

## Outputs / State Produced

- Structural decisions according to the current mode: decompose, create, update without
  structural change, or safely shrink work. An assessor-directed pass resolves every
  selected target before completion; initial analysis remains one root-level decision.
- Final response is treated as a summary of task changes/actions.
- After completion, the task tree must not be `None`.

**Mutation mechanism**: `TaskAnalyzerNode` task-structure tool calls directly mutate
`session.task` through TinyCUALoop task helpers; `TaskAnalyzerNode` does not return
opaque mutation instructions for TinyCUALoop to apply later.

## Tools

| Mode | Tool Scope |
|------|------------|
| `task_recreation` | TaskInit / TaskCreate tools allowed (LLM-assisted replacement). |
| `task_reanalysis` | Must NOT use TaskInit/TaskCreate tools; refines existing tree. |
| `initial_analysis` (after TaskCreate) | Must NOT use TaskInit/TaskCreate tools. |
| `effort_loop_decomposition` | Must NOT use TaskInit/TaskCreate tools. |
| `local_replan` | Must NOT use TaskInit/TaskCreate tools unless mode explicitly allows it. |

## Supported Modes

| Mode | Description |
|------|-------------|
| `initial_analysis` | First analysis pass after TaskCreateNode creates root task. |
| `recreation` | Full task tree rebuild/replacement (LLM-assisted). |
| `reanalysis` | Refine existing task tree without full replacement. |
| `effort_loop_decomposition` | Decompose tasks selected by TaskAssessor during effort passes. |
| `local_replan` | Local replan of active task or local region after ResultReviewer replan decision. |

## Queue Behavior / `on_complete()`

```text
TaskAnalyzerNode completes:
  → Advance queue; next node depends on upstream context:
     - After TaskCreate: next is AnalysisEffortNode
     - During effort pass: next is AnalysisEffortNode (continues effort loop)
     - After ResultReviewer replan: next is TaskExecutor
```

## Propagation

- Propagates task tree state changes.
- Final response is treated as a summary of task changes/actions.

## Failure / Retry Behavior

Retry according to `NodeRetryPolicy`. Recovery preserves the same structural alternatives
rather than preferring decomposition. If task tree is `None` after completion, that is a
contract violation.

## Related Config

- `NodeToolPolicy` — mode-dependent tool scope.
- `NodeRetryPolicy` — retry behavior.

## Related

- [`worker.md`](worker.md)
- [`analysis_effort.md`](analysis_effort.md)
- [`node.md`](node.md)
- [`../tools/task.md`](../tools/task.md)
