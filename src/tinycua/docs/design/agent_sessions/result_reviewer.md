# Result Reviewer

> **File:** `docs/design/agent_sessions/result_reviewer.md`
> **Package:** `tinycua.agent_nodes.result_reviewer`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`ResultReviewer` reviews task execution results. It normally receives
`TaskExecutorState` as YAML front-matter, but it may also receive a plain query.

It decides one of three actionable outcomes:

```text
RESULT_REVIEWER_CLASSIFICATION = ["accept", "retry", "replan"]
```

There is no `escalate_user`. If the reviewer cannot decide, it stays active with an
open question; the next user query passthrough routes back to this node.

---

## `run()` Method

```text
run(query: str) -> AsyncIterator[dict]
```

Flow:

```text
run(query)
  1. parsed_state = AgentState.from_string(query)
  2. if parsed_state is TaskExecutorState: render task/result/status as markdown
  3. build instruction: base + review rules + active task context
  4. build SDK Agent with specialized review toolset
  5. agent.run(query=query, messages=self.session.session_context, stream=True)
  6. ResultReviewLoop writes ResultReviewerState OR keeps reviewer active if no decision
```

---

## Specialized Review Toolset

ResultReviewer should have minimal write power.

```text
RESULT_REVIEWER_BASE_TOOLS = [
    *READ_ONLY_TASK_TOOLS,
    UpdateActiveTaskResult,      # for retry: reset active task to not_started + annotate context
    ReviewContextUpdateTool,     # specialized tool: [{"task_id": str, "context": str}]
    ClassificationTool(name="classify", labels=["accept", "retry", "replan"]),
]
```

It should not receive broad arbitrary edit tools unless explicitly injected for a
special review mode.

---

## Decision Semantics

| Decision | Meaning | Effect |
|----------|---------|--------|
| `accept` | Result is valid | Apply context updates to unfinished tasks, then continue to next active task or finish |
| `retry` | Recoverable issue | Set active task status to `not_started`; add retry context/instructions; route back to TaskExecutor |
| `replan` | Task decomposition is insufficient | Route `TaskAssessor → TaskAnalyzer`; active task may move/change |
| no decision | Reviewer cannot decide / asks open question | Keep ResultReviewer active; next user query passthrough returns here |

### Retry behavior

On retry:

```text
UpdateActiveTaskResult({
  "status": "not_started",
  "result": "Retry required: <reason>. Previous result: <summary>",
  "uncertainty_notes": [retry_instructions],
})
```

### Accept behavior

On accept, reviewer may update context for unfinished tasks only:

```text
context_updates = [
  {"task_id": "T-0.2", "context": "New context discovered from completed T-0.1..."}
]
```

Reviewer should avoid reading/updating previous completed tasks unless the input
explicitly requires it.

### Replan behavior

On replan, Worker orchestrates:

```text
ResultReviewerState(decision="replan")
  → TaskAssessor
  → TaskAnalyzer
  → TaskExecutor
```

The active task may change after reanalysis because DFS pre-order traversal may select

---

## Output: ResultReviewerState

```text
ResultReviewerState(
  type="result_reviewer",
  status="terminated" | "running" | "blocked",
  failure=N,
  decision="accept" | "retry" | "replan" | None,
  reason="...",
  confidence=0.9,
  context_updates=[{"task_id": "T-0.2", "context": "..."}],
  retry_instructions="...",
)
```

If `decision is None`, the reviewer did not terminate and remains active.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Three decisions | accept/retry/replan | Covers actionable outcomes |
| No escalate_user | Stay active + open question | HITL via passthrough, not special mode |
| Specialized write tools | Minimal review update surface | Reviewer should not arbitrarily rewrite tasks |
| Retry resets active task | status → `not_started` + context | Allows TaskExecutor to reattempt with guidance |
| Replan via Worker | Worker routes TaskAssessor → TaskAnalyzer | Replan is graph orchestration, not reviewer mutation |
| AgentState output | `ResultReviewerState` | Worker consumes typed state for routing |

---

## See also

Prev : [`TaskExecutor`](task_executor.md) | Next : [`PrimaryAgent`](primary_agent.md)

## Related

- [ResultReviewerState](../state/information.md#resultreviewerstate)
- [ReviewerDecision value object](../state/reviewer_decision.md)
- [TinyCUAWorker execution/review loop](../orchestration/worker.md#execution--review-loop)
- [Task review tools](../constants/tools.md)
