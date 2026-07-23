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
if route = task_creation:
    rootTask, summary ← TaskCreate(query)

// Step 2: Initial Decomposition
TaskAnalyze(rootTask, initial_analysis)

// Step 3: Effort-Gated Analysis Loop
passLimit ← EffortToLimit(effort);  pass ← 0
while pass < passLimit:
    selected ← TaskAssess(rootTask)
    if selected = ∅:
        break
    TaskAnalyze(selected, effort_loop);  pass ← pass + 1

// Step 4: Execute and Review Loop
active ← NextTask(rootTask)
while active ≠ null:
    result ← TaskExecute(active, context)
    decision ← ResultReview(result)
    if decision = replan:
        TaskAssess(active);  TaskAnalyze(active, local_replan)
        result ← TaskExecute(active, context)
        decision ← ResultReview(result)
    active ← NextTask(rootTask)

// Step 5: Aggregate Results
aggregatedResult ← Aggregate(rootTask)
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
The effort parameter maps to pass limits: none (0 passes, skip directly to execution), low (1 pass), medium (2 passes), high (3 passes). Each pass runs a TaskAssessor → TaskAnalyzer cycle. AnalysisEffortNode is deterministic and requires no LLM call.

### ResultReviewer Recovery Budget
Reviewer uses structured recovery budgets: 15 structured retries + 10 focused retries + 3 judge retries = 30 total per task. A same-error guard halts re-entry after 3 consecutive identical errors. Replan is capped by max_replans and scoped by replan_boundary.

### Task Execution Strategy
TaskExecutorNode uses ReAct framework (thought-act-observation loops) with write tool-calls. Execution stops when success criteria are met or a blocking issue is encountered. Post-order traversal is used for task tree execution.

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
| TaskExecutor execution failure | ResultReviewer decides: needs_revision, rejected, or replan |
| ResultReviewer needs_revision | Requeue [TaskExecutor, ResultReviewer] |
| ResultReviewer replan | Spawn [TaskAssessor, TaskAnalyzer(local_replan), TaskExecutor] |
| Same error raised 3× in succession | Take alternative action (replan or revised instructions) |
| Replan cap (max_replans) exceeded | Stop replanning; send back with explicit guidance or escalate |

---

## Output Naming

Save files as:
- `psudocode/task-processing.tex`
- `psudocode/task-processing.md`
