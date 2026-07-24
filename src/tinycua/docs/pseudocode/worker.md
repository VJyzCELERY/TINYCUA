# Algorithm 3: Worker Node

> **Methodology section pairing:** The prose below accompanies Algorithm 3
> in the paper. It covers design invariants and constraints that are not
> algorithmic and therefore remain outside the pseudocode block.

---

## Pseudocode (Algorithm 3)

**Input:** $\mathit{digestedContext}$, $\mathit{queue}$, $\mathit{existingWorker}$
**Output:** $\mathit{route}$, $\mathit{queue}$

```
// Step 1: Deduplication Check
if existingWorker != null:
    existingWorker.input ← digestedContext
    return

// Step 2: Task Existence Check
taskExists ← queue.hasTask()

// Step 3: Analysis Call
analysisResult ← SLMAnalyze(digestedContext, taskExists, queue)

// Step 4: Verdict / Classification
route ← Classify(analysisResult, taskExists, queue.hasWorkerSpawnedNodes())

// Step 5: RouteMap Dispatch
if route = task_creation:
    queue ← [TaskCreate, TaskAnalyzer, AnalysisEffort, TaskExecutor, ResultReviewer, Response]
elif route = task_recreation:
    remove all nodes after Worker from queue
    queue ← [TaskAnalyzer(+TaskInit), AnalysisEffort, TaskExecutor, ResultReviewer, Response]
elif route = task_reanalysis:
    remove all nodes after Worker from queue
    queue ← [TaskAnalyzer, AnalysisEffort, TaskExecutor, ResultReviewer, Response]
elif route = passthrough:
    queue ← [Response]
elif route = proceed_execution:
    queue ← [TaskExecutor, ResultReviewer, Response]
```

---

## Companion Prose (Not in Pseudocode)

The following design properties are described in the surrounding methodology
text and are **not** captured by the algorithm above:

### Transient Routing Node Behavior
Worker is a transient routing and continuation node. Its output becomes durable only when received by the next node and propagated upward as part of that node's input segment.

### Tool Constraint
Worker has access exclusively to worker decision tools. This constraint ensures the worker remains in its role as a routing decision-maker and does not perform task creation, analysis, execution, or review directly.

### Queue Non-Revealing
When the task tree is initially empty, only the `task_creation` route is exposed. Once a task exists, the remaining routes become available and `task_creation` is no longer a valid classification option.

### Worker Reuse
When QueryAnalyst routes to a WorkerNode that already exists in the queue, the Worker is not re-spawned. The forwarded input is assigned to the existing WorkerNode, which re-enters its classification logic.

### Queue Clearing on Recreation
When the `task_recreation` route is selected, all worker-spawned nodes after the current Worker are cleared. A new queue is then inserted by the route handler. The handler must ensure a terminal ResponseNode is present after clearing.

### Deduplication Policy
Worker enforces the same deduplication as QueryAnalyst: an existing node in the queue receives forwarded input rather than spawning a duplicate.

---

## Tool Permissions Summary

| Tool | Allowed | Purpose |
|------|---------|---------|
| Worker Decision Tools | Yes | Route classification and queue dispatch |
| TaskInit / TaskCreate | No | Owned by TaskCreateNode |
| Task Analysis Tools | No | Owned by TaskAnalyzerNode |
| Task Execution Tools | No | Owned by TaskExecutorNode |
| Review / Decision Tools | No | Owned by ResultReviewerNode |

---

## Retry Policy Summary

| Condition | Action |
|-----------|--------|
| Invalid or missing route label | Retry via NodeRetryPolicy (assistant-role continuation) |
| Analysis call failure | Retry with exponential backoff per policy |
| RouteMap dispatch to unknown label | Reject and re-classify |

---

## Output Naming

Save files as:
- `psudocode/worker.tex`
- `psudocode/worker.md`
