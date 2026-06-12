# Formula 2: Effort-Controlled Task Decomposition

## Definition

The effort parameter e ∈ {none, low, medium, high} controls how many analysis passes the TaskAnalyzerNode performs before execution begins. This is gated by the AnalysisEffortNode.

## Pass Limit Function

```
            ⎧ 0   if e = none
pass_limit(e) = ⎨ 1   if e = low
            ⎨ 2   if e = medium
            ⎩ 3   if e = high
```

## Decomposition Algorithm

The WorkerNode's `task_creation` route first calls TaskCreateNode for deterministic root task creation, then enters the effort-gated decomposition loop:

```
Algorithm: EffortControlledDecomposition

Input: initial_task, effort
Output: TaskTree (fully decomposed)

1.  TaskTree ← TaskCreateNode.create(initial_task)  // deterministic
2.  pass_count ← 0
3.  while pass_count < pass_limit(effort):
4.      tasks_to_decompose ← TaskAssessorNode.select(TaskTree)
5.      if tasks_to_decompose = ∅:
6.          break
7.      for task in tasks_to_decompose:
8.          TaskTree ← TaskAnalyzerNode.decompose(task)
9.      pass_count ← pass_count + 1
10. return TaskTree
```

## Properties

- **Deterministic control flow**: The loop itself involves no LLM calls beyond the decompose/select steps. The pass limit is a hard bound.
- **Progressive refinement**: Each pass refines the decomposition further. `none` = immediate execution (no decomposition), `high` = three rounds of analysis before execution.
- **Early termination**: If TaskAssessor finds no tasks needing further decomposition, the loop exits early regardless of pass limit.
- **Computational cost**: Higher effort = more LLM calls upfront, but potentially fewer retries during execution. The tradeoff is tunable per-query.

## Worker Route Variants

| Route | TaskCreate | TaskAnalyzer Mode | TaskInit Tools |
|-------|------------|-------------------|----------------|
| `task_creation` | Yes | initial | Yes |
| `task_recreation` | No | initial | Yes |
| `task_reanalysis` | No | initial | No |

## Complexity

Given |T| tasks and pass limit L:

- Worst case: O(L · |T|) TaskAnalyzerNode calls
- Best case: O(1) if TaskAssessor selects nothing on first pass
