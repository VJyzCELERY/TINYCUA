# Algorithm 1: TINYCUA Main Workflow

> Pseudocode derived from `TinyCUA_Architecture.png`

**Function:** `TinyCUA(UserQuery, SessionContext, Effort)`

**Input:**
- `UserQuery` — the raw user input
- `SessionContext` — structured session context (chat history + retrieved context)
- `Effort` — worker effort configuration controlling decomposition depth

**Output:**
- `Response` — the final user-facing answer

---

## Main Workflow

```
Function TinyCUA(UserQuery, SessionContext, Effort):

    ─────────────────────────────────────────────
    PHASE 1: Query Analyst
    ─────────────────────────────────────────────

    EnhancedQuery, Route = QueryAnalystNode(UserQuery, SessionContext)

    if Route == Passthrough:
        return ResponseNode(EnhancedQuery, SessionContext)

    ─────────────────────────────────────────────
    PHASE 2: Information Digester
    ─────────────────────────────────────────────

    DigestedInformation = InformationDigesterNode(EnhancedQuery, SessionContext)

    ─────────────────────────────────────────────
    PHASE 3: Worker Routing
    ─────────────────────────────────────────────

    WorkerRoute = WorkerNode(DigestedInformation)

    if WorkerRoute == Passthrough:
        return ResponseNode(DigestedInformation, SessionContext)

    ─────────────────────────────────────────────
    PHASE 4: Task Tree Creation
    ─────────────────────────────────────────────

    if WorkerRoute == TaskCreation:
        TaskTree = TaskCreateNode(DigestedInformation, Effort)

    else if WorkerRoute in {TaskRecreation, TaskReanalysis}:
        TaskTree = TaskAnalyzerNode(DigestedInformation)

    ─────────────────────────────────────────────
    PHASE 5: Analysis-Effort Loop
    ─────────────────────────────────────────────

    PassCount = 0
    PassLimit = AnalysisEffortNode(Effort)

    while PassCount < PassLimit:

        SelectedTasks = TaskAssessorNode(TaskTree)

        if SelectedTasks is empty:
            break

        for each Task in SelectedTasks:
            Children = TaskAnalyzerNode(Task.Context)
            AttachChildren(TaskTree, Task, Children)

        PassCount = PassCount + 1

    ─────────────────────────────────────────────
    PHASE 6: Sequential Task Execution Loop
    ─────────────────────────────────────────────

    while exists unfinished leaf task in TaskTree:

        Task = SelectNextUnfinishedLeaf(TaskTree)
        Result = TaskExecutorNode(Task, ShallowRoadmap(TaskTree))

        Review = ResultReviewerNode(
            Task,
            Result,
            ExecutionLog(Task),
            ShallowRoadmap(TaskTree)
        )

        if Review.Status == Accept:

            if Review.RootDone:
                PropagateContext(TaskTree, Task, Review)
                MarkAccepted(TaskTree, Task, Result, Review)
                break

            else:
                PropagateContext(TaskTree, Task, Review)
                MarkAccepted(TaskTree, Task, Result, Review)
                // continue to next task

        else if Review.Status == Retry:
            RecordFailureContext(Task, Review)
            // retry same task

        else if Review.Status == Replan:
            Subtasks = TaskAnalyzerNode(Task.Context, Review.Rationale)
            ReplaceLeafWithSubtasks(TaskTree, Task, Subtasks)
            // re-enter decomposition loop
            PassCount = 0
            PassLimit = AnalysisEffortNode(Effort)
            while PassCount < PassLimit:
                SelectedTasks = TaskAssessorNode(TaskTree)
                if SelectedTasks is empty:
                    break
                for each SelectedTask in SelectedTasks:
                    Children = TaskAnalyzerNode(SelectedTask.Context)
                    AttachChildren(TaskTree, SelectedTask, Children)
                PassCount = PassCount + 1

    ─────────────────────────────────────────────
    PHASE 7: Result Aggregation and Response
    ─────────────────────────────────────────────

    AggregatedResult = ResultAggregationNode(TaskTree)
    return ResponseNode(AggregatedResult)
```

---

## Flow Summary

| Phase | Node | Type | Output |
|-------|------|------|--------|
| 1 | QueryAnalystNode | DecisionNode | `EnhancedQuery`, `Route` |
| 2 | InformationDigesterNode | ProcessNode | `DigestedInformation` |
| 3 | WorkerNode | DecisionNode | `WorkerRoute` |
| 4 | TaskCreateNode / TaskAnalyzerNode | ProcessNode | `TaskTree` |
| 5 | AnalysisEffortNode → TaskAssessorNode → TaskAnalyzerNode | ProcessNode (loop) | Decomposed `TaskTree` |
| 6 | TaskExecutorNode → ResultReviewerNode | ProcessNode (loop) | Approved task `Result`s |
| 7 | ResultAggregationNode → ResponseNode | ProcessNode (terminal) | `Response` |

---

## Routing Edges

| From | Edge Label | To |
|------|------------|-----|
| QueryAnalystNode | `passthrough` | ResponseNode |
| QueryAnalystNode | `enhanced query` | InformationDigesterNode |
| InformationDigesterNode | `digested information` | WorkerNode |
| WorkerNode | `passthrough` | ResponseNode |
| WorkerNode | `task_creation` | TaskCreateNode |
| WorkerNode | `task_recreation / task_reanalysis` | TaskAnalyzerNode |
| TaskCreateNode | — | TaskAnalyzerNode |
| TaskAnalyzerNode | — | AnalysisEffortNode |
| AnalysisEffortNode | `pass < limit` | TaskAssessorNode |
| AnalysisEffortNode | `pass >= limit` | TaskExecutorNode |
| TaskAssessorNode | — | TaskAnalyzerNode |
| TaskExecutorNode | `more tasks` | TaskExecutorNode |
| TaskExecutorNode | — | ResultReviewerNode |
| ResultReviewerNode | `accept (next task)` | TaskExecutorNode |
| ResultReviewerNode | `retry` | TaskExecutorNode |
| ResultReviewerNode | `replan` | TaskAssessorNode |
| ResultReviewerNode | `accept (root done)` | ResultAggregationNode |
| ResultAggregationNode | — | ResponseNode |
| ResponseNode | `response` | User |
