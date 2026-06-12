# Formula 4: Review Loop with Failure Threshold

## Definition

The review loop governs retry behavior, preventing infinite loops while allowing transient failures.

## Variables

| Variable | Type | Description |
|----------|------|-------------|
| `consecutive_failures` | ℕ₀ | Count of consecutive retry outcomes |
| `threshold` | ℕ | Maximum consecutive failures before escalation (default: 5) |

## Review Loop Algorithm

```
Algorithm: ReviewLoop

Input: task, threshold
Output: task_result | escalated

1.  consecutive_failures ← 0
2.  loop:
3.      result ← TaskExecutorNode.execute(task)
4.      decision ← ResultReviewerNode.review(task, result)
5.      match decision:
6.          case accept:
7.              consecutive_failures ← 0
8.              update task status/result
9.              if root task done:
10.                 advance to ResultAggregationNode
11.             else:
12.                 advance to next TaskExecutorNode
13.         case retry:
14.             consecutive_failures ← consecutive_failures + 1
15.             if consecutive_failures ≥ threshold:
16.                 escalate to user
17.             else:
18.                 record failure context in task
19.                 re-execute same task
20.         case replan:
21.             spawn TaskAssessorNode (scope: active task)
22.             spawn TaskAnalyzerNode (mode: local_replan)
23.             re-execute
24.         case open_question:
25.             install mandatory_passthrough
26.             pause and wait for user continuation
```

## Decision Semantics

| Decision | Meaning | Recovery |
|----------|---------|----------|
| `accept` | Result meets quality bar | Reset counter, advance to next task or aggregation |
| `retry` | Transient failure, same plan viable | Increment counter, re-execute with failure context |
| `replan` | Plan failure | Local TaskAssessor + TaskAnalyzer, then re-execute |
| `open_question` | Uncertainty requiring user input | Mandatory passthrough, await continuation |

## Threshold Justification

The default threshold of 5 was chosen empirically:

- < 3: Too aggressive — transient failures (network, rate limits) cause premature escalation
- \> 7: Too lenient — wastes compute on likely-futile retries
- = 5: Balanced — allows recovery from transient issues while capping waste

## Key Constraint

Replan is a **local execution-time recovery** path. It MUST NOT spawn AnalysisEffortNode and MUST NOT run the Worker-owned effort-gated decomposition loop. Replan uses TaskAssessorNode with scope limited to the active task or local region, and TaskAnalyzerNode with mode `local_replan`.

## Properties

- **Liveness guarantee**: The loop terminates in finite time (either success, escalation, or user pause).
- **Reset semantics**: A successful review resets the counter, allowing later tasks to have their own failure budget.
- **Replan scope**: Replan is local to the current task, not a global re-decomposition.
