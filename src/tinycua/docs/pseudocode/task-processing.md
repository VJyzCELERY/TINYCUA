# Algorithm 3: Task Processing

> **Methodology section pairing:** The prose below accompanies Algorithm 3
> in the paper. It covers design invariants and constraints that are not
> algorithmic and therefore remain outside the pseudocode block.

---

## Pseudocode (Algorithm 3)

**Input:** $\mathit{route}$, $\mathit{queue}$, $\mathit{effort}$
**Output:** $\mathit{aggregatedResult}$

```
// Step 1: Task Creation
1:  if route = task_creation then
2:      rootTask, summary ← TaskCreate(query)
3:  end if

// Step 2: Initial Decomposition
4:  TaskAnalyze(rootTask, initial_analysis)

// Step 3: Effort-Gated Analysis Loop
5:  pass ← 0
6:  while AnalysisEffort(effort, pass) = continue do
7:      selected ← TaskAssess(rootTask);   if selected = NULL then break
8:      TaskAnalyze(selected, effort_loop);   pass ← pass + 1
9:  end while

// Step 4: Execute and Review Loop
10: completedResults ← NULL
11: active ← NextTask(rootTask)
12: while active ≠ NULL do
13:     context ← BuildContext(active, completedResults)
14:     result ← TaskExecute(active, context);   retries ← 0
15:     decision ← ResultReview(result)
16:     while decision = reject ∧ retries < retryLimit do
17:         result ← TaskExecute(active, context);   retries ← retries + 1;   decision ← ResultReview(result)
18:     end while
19:     if decision = replan then
20:         TaskAssess(active);   TaskAnalyze(active, replan);   result ← TaskExecute(active, context)
21:     if decision = accept then
22:         completedResults ← completedResults ∪ {result};   active ← NextTask(rootTask)
23: end while

// Step 5: Aggregate Results
24: aggregatedResult ← Aggregate(rootTask)
```

---

## Companion Prose (Not in Pseudocode)

The following design properties are described in the surrounding methodology
text and are **not** captured by the algorithm above:

### Task Analyzer Modes
TaskAnalyzerNode operates in five modes: initial_analysis (first-pass after root creation), recreation (full tree rebuild), reanalysis (refinement without replacement), effort_loop_decomposition (tasks selected during effort passes), and local_replan (execution-time recovery from ResultReviewer). Mode selection is determined by upstream context, not by the analyzer itself.

### Sibling Context Propagation
Each subtask $t_i$ receives context $C(t_i) = \text{Decompose}(t_i) \cup \bigcup_{j=1}^{i-1} R(t_j)$, where $R(t_j)$ is the result summary from previously completed siblings. This ensures execution operates within a task-relevant information boundary.

### Result Aggregation
When all subtasks complete, results aggregate upward: $R(T) = \text{Aggregate}(\bigcup_{i=1}^{n} R(t_i))$. Only results from completed siblings and a task's own subtask outputs are included.

### Analysis Effort Levels
The effort parameter controls planning depth via AnalysisEffortNode, a deterministic decision node. Effort levels: none (skip to execution), low (1 pass), medium (2 passes), high (3 passes). Each pass runs a TaskAssessor → TaskAnalyzer cycle. The node gates whether to continue analysis (pass < limit) or proceed to execution (pass ≥ limit).

### ResultReviewer Recovery Budget
Reviewer uses structured recovery budgets: 15 structured retries + 10 focused retries + 3 judge retries = 30 total per task. A same-error guard halts re-entry after 3 consecutive identical errors. Replan is capped by max_replans and scoped by replan_boundary. The three decision categories are:
- **Accept**: task advances; if root task, proceeds to aggregation
- **Reject**: task is retried up to retryLimit; beyond limit, escalates to replan
- **Replan**: task is sent to TaskAssessor → TaskAnalyzer for decomposition before re-execution

### Task Execution Strategy
TaskExecutorNode uses ReAct framework (thought-act-observation loops) with write tool-calls. Execution stops when success criteria are met or a blocking issue is encountered. Post-order traversal is used for task tree execution. The executor processes tasks sequentially, yielding to ResultReviewerNode after each task completion.

### Route Handling
When route is task_recreation or task_reanalysis, the existing task tree is passed to TaskAnalyzerNode directly (TaskCreateNode is skipped). When route is proceed_execution, the queue proceeds directly to TaskExecutorNode (planning phase is skipped).

The WorkerNode dispatches different node sequences depending on the selected route:

| Route | Queue Contents | Description |
|-------|---------------|-------------|
| task_creation | TaskCreate → TaskAnalyzer → AnalysisEffort → TaskExecutor → ResultReviewer → Response | Full planning pipeline from scratch |
| task_reanalysis | TaskAnalyzer → AnalysisEffort → TaskExecutor → ResultReviewer → Response | Clear stale nodes, re-analyze existing tree |
| task_recreation | TaskAnalyzer(+TaskInit) → AnalysisEffort → TaskExecutor → ResultReviewer → Response | Clear stale nodes, rebuild tree from init |
| proceed_execution | TaskExecutor → ResultReviewer → Response | Skip planning, execute existing tree |
| passthrough | Response | Return immediately without task processing |

For task_recreation and task_reanalysis, the WorkerNode first removes all previously queued nodes that followed it (clearing the old plan), then inserts the new node sequence. This ensures no stale planning artifacts remain in the queue.

---

## Tool Permissions Summary

| Tool | Allowed | Purpose |
|------|---------|---------|
| TaskInit / TaskCreate | Conditional | Root task creation only (TaskCreateNode) |
| Task Analysis Tools | Conditional | Decomposition and refinement (TaskAnalyzerNode) |
| Task Assessment Tools | Conditional | Select unfinished tasks (TaskAssessorNode) |
| Task Execution Tools | Conditional | Execute active task via ReAct (TaskExecutorNode) |
| Review / Decision Tools | Conditional | Evaluate execution results (ResultReviewerNode) |
| Read-only Tree Inspection | Conditional | Aggregate results (ResultAggregationNode) |

---

## Retry Policy Summary

| Condition | Action |
|-----------|--------|
| TaskAnalyzer completes with null tree | Contract violation; retry per NodeRetryPolicy |
| TaskExecutor execution failure | ResultReviewer decides: accept, reject, or replan |
| ResultReviewer reject | Requeue TaskExecutor for same task (up to retryLimit) |
| ResultReviewer replan | Spawn [TaskAssessor, TaskAnalyzer(replan), TaskExecutor] |
| Same error raised 3× in succession | Take alternative action (replan or revised instructions) |
| Replan cap (max_replans) exceeded | Stop replanning; send back with explicit guidance or escalate |

---

## Output Naming

Save files as:
- `pseudocode/task-processing.tex`
- `pseudocode/task-processing.md`
