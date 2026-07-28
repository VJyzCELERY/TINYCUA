# Task

> **Package:** `tinycua.models.task`
> **Status:** Target architecture

## Role

Task models represent worker task trees, active tasks, task results, and task sharing.
Every task is a recursively refinable outcome at its current planning resolution. It may
remain directly executable or gain children when decomposition later provides a material
execution or review benefit. Children are scoped contributions rather than replacements;
after they complete, the parent remains available for integration and verification.

```text
Task
  · task_id: str
  · title: str
  · description: str
  · status: Literal["pending", "in_progress", "blocked", "done", "failed"]
  · children: list[Task]
  · active_child_id: str | None
  · result: TaskResult | None
  · metadata: dict

TaskResult
  · task_id: str
  · execution_status: Literal["not_started", "running", "succeeded", "failed", "blocked"]
  · reviewer_decision: ReviewerDecision | None
  · summary: str
  · artifacts: list[dict]
  · metadata: dict
```

`TaskResult.execution_status` describes task execution state. Review outcomes use the
canonical `ReviewerDecision` values (`accept`, `retry`, `replan`, `open_question`) and are
stored separately in `reviewer_decision`.

Task sharing remains explicit. Child/per-node sessions do not automatically inherit a
task unless TinyCUA assigns or scopes it.

Task replacement propagation follows session/task sharing rules and MUST NOT cross
configured boundaries.

## Acceptance Context

The root task retains the request's acceptance criteria as immutable prompt context so
later nodes do not lose the original goal. Child tasks do not own individual criteria,
and task completion does not require structured clause coverage or evidence metadata.

## Active Task Selection

Active task selection uses DFS pre-order traversal of the root Task tree:

```text
TinyCUALoop.get_active_task() -> Task | None
TinyCUALoop.set_active_task(task_id) -> None
TinyCUALoop.update_active_task_result(...)
```

Active task is resolved by DFS pre-order traversal of the root Task tree. The first
unfinished task matching the active-task predicate is selected. `active_child_id` is a
traversal hint maintained by the loop.

## Active Task Handoff Protocol

This section consolidates the end-to-end handoff contract across the task model,
TaskExecutor, and ResultReviewer. See also
[`../loops/task_executor.md`](../loops/task_executor.md) and
[`../loops/result_reviewer.md`](../loops/result_reviewer.md).

```text
TinyCUALoop owns root task and active task id.

Before TaskExecutor runs:
  1. TinyCUALoop resolves get_active_task().
  2. Injects a read-only active task reference/id into NodeInput.
  3. TaskExecutor receives the active task snapshot/id (read-only).

TaskExecutor emits result:
  4. Execution result is tagged with the active task id.

ResultReviewer decides:
  5. accept: Recomputes the next DFS active task.
     - If root task done → advance to ResultAggregationNode → ResponseNode.
     - If root task not done → advance to TaskExecutor (next active task).
  6. retry: Preserves the same active task; advances to TaskExecutor (retry).
  7. open_question: Preserves the same active task; keeps ResultReviewer active
     with mandatory_passthrough targeting this node/session.
  8. replan: Recomputes after local task updates (TaskAssessor + TaskAnalyzer).
```

### Ownership Rules

- **TinyCUALoop / task helpers**: Own the root task tree and current active task id.
  Own task interaction helpers. Can select, set, and update active task.
- **TaskExecutor**: Receives active task as input. May report results for sibling tasks
  via `task_result_update` (FR-069); must `task_inspect` siblings first. Must not select
  the active task.
- **ResultReviewer**: Updates active task status/result based on review decision.
  Can trigger active task recomputation (accept, replan) or preserve it (retry,
  open_question). Must not mutate task tree structure beyond status/result updates.

## TaskTree Completion/Update Rules

On `ResultReviewer` accept:

```text
on_result_reviewer_accept(active_task):
  1. Mark current task result as accepted.
  2. Update active task context/result.
  3. If current task is complete, go up to parent.
     - If no parent exists, root task is done; route to ResultAggregationNode.
  4. If current task is unfinished, DFS pre-order to the next unfinished child.
  5. If no unfinished child exists:
     - If current task has no children, execute current task.
     - If all children complete, re-evaluate current task completion.
       - If complete, mark complete and continue upward.
       - If incomplete, update task instruction/context and execute current task.
```

## Related

- [`session.md`](session.md)
- [`reviewer_decision.md`](reviewer_decision.md)
- [`../tools/task.md`](../tools/task.md)
- [`../loops/worker_concept.md`](../loops/worker_concept.md)
