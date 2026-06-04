# TinyCUAResultReviewerNode

> **Package:** `tinycua.loops.result_reviewer`
> **Status:** Target architecture

## Role

`TinyCUAResultReviewerNode` is a concrete `ProcessNode` that evaluates TaskExecutor
output and decides whether to accept, retry, replan, or ask an open question. It is the
quality gate between execution and response.

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

- `ReviewerDecision` with one of: `accept`, `retry`, `replan`, `open_question`.
- Updated active `TaskResult` and task context.

## Tools

| Tool Scope | Description |
|------------|-------------|
| Review decision tools | Evaluate executor output and produce reviewer decision. |
| Task result / context update tools | Update active task result and context based on decision. |

## Reviewer Decisions

| Decision | Behavior |
|----------|----------|
| `accept` | Semantic check passes; update active task status/result to accepted. |
| `retry` | Plan is solid but execution result does not satisfy success criteria. |
| `replan` | Executor result indicates current plan/task decomposition should change. |
| `open_question` | Reviewer remains active; installs mandatory passthrough for user input. |

## Retry / Failure Threshold

- Failure count is tracked at `TinyCUALoop` or root-session level.
- Default threshold: 5 retries, default 5 when not configured.
- Configurable via review configuration.
- Failure count resets after a successful `accept` decision.
- When threshold is reached, retrying stops and the reviewer must escalate or accept.

## Queue Behavior / `on_complete()`

```text
ResultReviewer completes:
  accept:
    → Update active task status/result
    → If root task done:
        advance to ResultAggregationNode → ResponseNode
    → If root task not done:
        advance to TaskExecutor (next active task)

  retry:
    → Advance to TaskExecutor (retry same task)

  replan:
    → Spawn/prepend TaskAssessor(scope=active_task_or_local_region)
    → TaskAnalyzer(mode=local_replan, init_enabled=false)
    → TaskExecutor

  open_question:
    → Keep ResultReviewer active
    → Install mandatory_passthrough targeting this ResultReviewer node/session
```

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

## Propagation

- Propagates reviewer decision to downstream nodes.
- On `open_question`, propagates continuation prompt for user input.

## Failure / Retry Behavior

- Failure count tracked at loop/root-session level.
- Reset on success (`accept`).
- Stop retrying when configurable threshold is reached (default: 5).

## Related Config

- `ReviewerRetryThreshold` — configurable failure threshold (default: 5).
- `NodeRetryPolicy` — retry behavior.
- `NodeToolPolicy` — review decision and task update tools.

## Related

- [`node.md`](node.md)
- [`../models/reviewer_decision.md`](../models/reviewer_decision.md)
- [`../tools/task.md`](../tools/task.md)
