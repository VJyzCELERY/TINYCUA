# TinyCUAResultReviewerNode

> **Package:** `tinycua.loops.result_reviewer`
> **Status:** Target architecture

## Role

`TinyCUAResultReviewerNode` is a concrete `ProcessNode` that reviews TaskExecutor
output and records a free-form report plus a decision to approve, revise, replan,
postpone, or compromise.

## Non-Responsibilities

- Does not execute tasks (that belongs to TaskExecutor).
- Does not decompose or analyze tasks for replan (replan spawns TaskAssessor +
  TaskAnalyzer).
- Does not synthesize final user responses (that belongs to ResponseNode).

## Inputs

- TaskExecutor execution result.
- Active task context and result.
- Bounded executor evidence: tool name, command/path/URL/query, success, exit code,
  error, and audit reference when available. Tool output bodies are not replayed.

See the full handoff protocol in
[`../models/task.md`](../models/task.md#active-task-handoff-protocol).

## Outputs / State Produced

- `ReviewerDecision` with one of: `approved`, `needs_revision`, `replan`,
  `postpone_siblings`, `postpone_final`, `compromise`,
  plus a concise free-form report.
- Updated active `TaskResult` and task context.

Acceptance criteria remain visible as immutable root-task context. They are advisory
while reviewing a leaf and become semantic gates when reviewing the root. The reviewer
matches behavioral claims to focused runtime checks, artifact claims to inspection, and
external claims to authoritative sources. This semantic coverage is not a machine-enforced
clause-proof protocol.

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
| `replan` | Executor result indicates current plan/task decomposition should change. |
| `postpone_siblings` | Defer non-root blocked work until its normal siblings finish or defer. |
| `postpone_final` | On revisit, defer work until the global final drain. |
| `compromise` | Preserve a failed non-empty result and rationale as a terminal limitation. |

Stored legacy `rejected` decisions retain `needs_revision` behavior but are not offered
by model-facing tools or guidance.

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
    → [TaskExecutor, ResultReviewer]              # verify/refresh, then review

  has result + needs_revision:
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

> **plan_unchanged (FR-051):** if the replan pass produces no structural change, the
> existing executor boundary remains so it can verify or refresh the result before the
> reviewer runs again.
>
> **replan_boundary + max_replans (FR-049 / FR-050):** replan is scoped by
> `replan_boundary` (default: the active task and its local region) and capped by
> `max_replans` per task. When the cap is reached, the reviewer MUST stop replanning
> and either send back for revision with explicit guidance or escalate.

## Propagation

- Propagates reviewer decision to downstream nodes.
- On `needs_revision`, propagates revision instructions to TaskExecutor.
- On `replan`, propagates the local replan scope to TaskAssessor + TaskAnalyzer.
- On postponement or compromise, schedules from the explicit reviewed task decision,
  not the newly active task.

## Related Config

- `NodeRetryPolicy` — retry behavior.
- `NodeToolPolicy` — review decision and task update tools.
- Review recovery budgets (FR-060/063), same-error guard (FR-078), `max_replans`
  (FR-050), `replan_boundary` (FR-049).

## Related

- [`node.md`](node.md)
- [`../models/reviewer_decision.md`](../models/reviewer_decision.md)
- [`../tools/task.md`](../tools/task.md)
