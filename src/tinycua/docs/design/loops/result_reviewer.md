# TinyCUAResultReviewerNode

> **Package:** `tinycua.loops.result_reviewer`
> **Status:** Target architecture

## Role

`TinyCUAResultReviewerNode` is a concrete `ProcessNode` that reviews TaskExecutor
output and records a free-form report plus a decision to approve, send back for
revision, or replan.

## Non-Responsibilities

- Does not execute tasks (that belongs to TaskExecutor).
- Does not decompose or analyze tasks for replan (replan spawns TaskAssessor +
  TaskAnalyzer).
- Does not synthesize final user responses (that belongs to ResponseNode).

## Inputs

- TaskExecutor execution result.
- Active task context and result.

See the full handoff protocol in
[`../models/task.md`](../models/task.md#active-task-handoff-protocol).

## Outputs / State Produced

- `ReviewerDecision` with one of: `approved`, `needs_revision`, `rejected`, `replan`,
  plus a concise free-form report.
- Updated active `TaskResult` and task context.

Acceptance criteria remain visible as immutable root-task context. They guide the
review but are not machine-enforced coverage or evidence gates.

## Tools

| Tool Scope | Description |
|------------|-------------|
| Review decision tools | Record the reviewer report and decision. |
| Task result / context update tools | Update active task result and context based on decision. |

## Reviewer Decisions

| Decision | Behavior |
|----------|----------|
| `approved` | Semantic check passes; update active task status/result to approved. |
| `needs_revision` | Plan is solid but execution result does not satisfy success criteria; send back for revision. |
| `rejected` | Alias for `needs_revision` (FR-057). Treated identically by the loop. |
| `replan` | Executor result indicates current plan/task decomposition should change. |

> `open_question` is off by default (FR-057). When enabled via config, the reviewer
> stays active and installs a mandatory passthrough for user input.

## Recovery Model (FR-060 / FR-063)

The reviewer uses a structured recovery budget instead of a single retry counter:

- Per-method budgets: 15 structured retries + 10 focused retries + 3 judge retries = 30
  total per task.
- Partial results are preserved across re-entries.
- `accumulated_tool_results` persists across re-entries so revisited work is not lost.
- A no-progress guard halts re-entry when no new information has been produced since the
  last attempt.
- Re-entries into the same task are unlimited until a budget is exhausted or the
  no-progress guard fires.

### Same-Error Guard (FR-078)

When the same error is raised 3× in succession, the reviewer MUST take an alternative
action (replan or send back with a different instruction) rather than retrying again.

## Queue Behavior / `on_complete()` (FR-067)

Queue shape is state-driven, not label-driven. The reviewer inspects the active task's
current state and selects the next nodes accordingly:

```text
ResultReviewer completes:
  no result yet:
    → [TaskExecutor, ResultReviewer]              # execute then review again

  has result, no negative review:
    → [ResultReviewer] only                        # re-confirm, then proceed

  has result + needs_revision / rejected:
    → [TaskExecutor, ResultReviewer]              # revise then re-review

  failed result:
    → [TaskExecutor, ResultReviewer]              # recover then re-review

  all done (root task complete):
    → [ResultAggregationNode]                     # advance to aggregation
```

### Approved-But-Not-Completed Safety Net (FR-079)

If a task is marked `approved` but its `TaskResult` is not actually complete (e.g. the
reviewer approved prematurely or a sibling surfaced missing work), the reviewer MUST
re-open the task: clear the approval, restore the prior state, and requeue
`[TaskExecutor, ResultReviewer]` instead of advancing to aggregation.

### Replan Path

Replan is a local execution-time recovery path, NOT a full upfront planning process.
The replan path MUST NOT spawn `AnalysisEffortNode` and MUST NOT run the Worker-owned
effort-gated upfront TaskAnalysisLoop.

```text
ResultReviewer replan:
  TaskAssessor(scope=active_task_or_local_region)
  → TaskAnalyzer(mode=local_replan, init_enabled=false)
  → TaskExecutor
```

> **plan_unchanged skip (FR-051):** if the replan pass produces no change to the active
> task's plan, the reviewer skips re-execution and falls back to `needs_revision` with
> updated instructions rather than looping.
>
> **replan_boundary + max_replans (FR-049 / FR-050):** replan is scoped by
> `replan_boundary` (default: the active task and its local region) and capped by
> `max_replans` per task. When the cap is reached, the reviewer MUST stop replanning
> and either send back for revision with explicit guidance or escalate.

## Propagation

- Propagates reviewer decision to downstream nodes.
- On `needs_revision` / `rejected`, propagates revision instructions to TaskExecutor.
- On `replan`, propagates the local replan scope to TaskAssessor + TaskAnalyzer.

## Related Config

- `NodeRetryPolicy` — retry behavior.
- `NodeToolPolicy` — review decision and task update tools.
- Review recovery budgets (FR-060/063), same-error guard (FR-078), `max_replans`
  (FR-050), `replan_boundary` (FR-049).

## Related

- [`node.md`](node.md)
- [`../models/reviewer_decision.md`](../models/reviewer_decision.md)
- [`../tools/task.md`](../tools/task.md)
