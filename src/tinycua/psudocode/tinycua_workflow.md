# TINYCUA Workflow Pseudocode

> **Purpose:** Algorithmic explanation of the TINYCUA main workflow for architecture documentation.

---

## Overview

TINYCUA routes each user query through a lightweight Query Analyst. Simple requests pass directly to response synthesis. Work-intensive requests are first condensed by the Information Digester, then processed by a Worker that creates a task tree, executes only leaf tasks, reviews every task result, propagates accepted context to future tasks, and aggregates accepted results before producing the final response.

---

## Algorithm 1: TINYCUA Main Workflow

```python
def TinyCUA(q: UserQuery, C: SessionContext, effort: WorkerEffort) -> Response:
    """
    Main entry point for TINYCUA workflow.
    
    Args:
        q: User query
        C: Session context (chat_history + context)
        effort: Worker effort configuration
        
    Returns:
        Final user response
    """
    # Step 1: Query Analyst - High-level context scan and classification
    q_enhanced, route = QueryAnalyst(q, C)
    
    # Step 2: Route decision
    if route == PASSTHROUGH:
        return ResponseNode(q_enhanced, C)
    
    # Step 3: Information Digester - Deep context retrieval and condensation
    digest = InformationDigester(q_enhanced, C)
    
    # Step 4: Worker Route decision
    worker_route = WorkerRoute(digest)
    
    if worker_route == PASSTHROUGH:
        return ResponseNode(digest, C)
    
    # Step 5: Task Tree Creation (if needed)
    if worker_route == TASK_CREATION:
        task_tree = CreateTaskTree(digest, effort)
    elif worker_route in {TASK_RECREATION, TASK_REANALYSIS}:
        task_tree = TaskAnalyzer(digest, task_tree)
    
    # Step 6: Execute tasks sequentially
    while HasUnfinishedLeafTasks(task_tree):
        # Select next leaf task
        task = SelectNextUnfinishedLeaf(task_tree)
        
        # Execute task with shallow roadmap awareness
        result = TaskExecutor(task, ShallowRoadmap(task_tree))
        
        # Review result
        review = ResultReviewer(
            task, 
            result, 
            ExecutionLog(task), 
            ShallowRoadmap(task_tree)
        )
        
        # Handle review decision
        if review.status == APPROVED:
            PropagateContext(task_tree, task, review)
            MarkAccepted(task_tree, task, result, review)
        
        elif review.status in {NEEDS_REVISION, REJECTED}:
            RecordFailureContext(task, review)
            # Continue to next iteration (retry)
        
        elif review.status == REPLAN:
            # Decompose current task into subtasks
            subtasks = TaskAnalyzer(task.context, review.rationale)
            ReplaceLeafWithSubtasks(task_tree, task, subtasks)
    
    # Step 7: Aggregate results and generate response
    aggregate = ResultAggregationNode(task_tree)
    return ResponseNode(aggregate)
```

---

## Algorithm 2: Task Tree Creation

```python
def CreateTaskTree(digest: DigestedInformation, effort: WorkerEffort) -> TaskTree:
    """
    Create a nested task tree through iterative decomposition.
    
    Args:
        digest: Condensed context from Information Digester
        effort: Controls decomposition depth
        
    Returns:
        Nested task tree with leaf and container tasks
    """
    # Initial pass: Create base task list
    task_tree = TaskAnalyzer(digest)
    
    # Get maximum decomposition passes from effort setting
    pass_limit = AnalysisEffortNode(effort)
    
    # Iterative decomposition loop
    for pass_num in range(1, pass_limit + 1):
        # Task Assessor selects tasks for decomposition
        selected_tasks = TaskAssessor(task_tree)
        
        # Stop if no tasks need decomposition
        if not selected_tasks:
            break
        
        # Decompose each selected task
        for task in selected_tasks:
            children = TaskAnalyzer(task.context)
            AttachChildren(task_tree, task, children)
    
    return task_tree
```

---

## Algorithm 3: Query Analyst

```python
def QueryAnalyst(q: UserQuery, C: SessionContext) -> Tuple[CEQ, Classification]:
    """
    Fast, high-level context scan and routing decision.
    
    Args:
        q: User query
        C: Session context
        
    Returns:
        Context Enhanced Query (CEQ) and routing classification
    """
    # High-level context scan (no deep retrieval)
    ceq = EnhanceQuery(q, C.chat_history, C.context)
    
    # Classify request complexity
    classification = ClassifyRequest(ceq)
    
    # Validate classification with safeguards
    ValidateClassification(classification)
    
    return ceq, classification
```

---

## Algorithm 4: Information Digester

```python
def InformationDigester(ceq: CEQ, C: SessionContext) -> DigestedInformation:
    """
    Explore session context to find relevant lower-level details.
    
    Args:
        ceq: Context Enhanced Query from Query Analyst
        C: Session context
        
    Returns:
        Precision-oriented digested information
    """
    # Identify information gaps in the query
    gaps = IdentifyInformationGaps(ceq)
    
    # Enhanced Context Retrieval - search session context
    retrieved_context = EnhancedContextRetrieval(gaps, C.context)
    
    # Extract and filter relevant information
    relevant_topics = IdentifyRelevantTopics(retrieved_context)
    extracted = ExtractRelevantContext(retrieved_context, relevant_topics)
    filtered = RemoveDistractingContext(extracted)
    
    # Preserve task-critical details
    preserved = PreserveTaskCriticalDetails(filtered)
    
    # Structure digest with advisory instructions
    digest = StructureDigest(preserved, advisory_instructions=True)
    
    return digest
```

---

## Algorithm 5: Task Executor (ReAct Loop)

```python
def TaskExecutor(task: Task, roadmap: ShallowRoadmap) -> TaskResult:
    """
    Execute a single task using ReAct pattern.
    
    Args:
        task: Current task with context and success criteria
        roadmap: Shallow task list for scope awareness
        
    Returns:
        Task result with status and output
    """
    # Initialize execution state
    execution_log = ExecutionLog()
    accumulated_results = []
    
    while True:
        # Think: Plan short-term action
        action = Think(task, accumulated_results, roadmap)
        
        # Act: Execute tool or reasoning step
        observation = Act(action, task.context)
        
        # Observe: Record result
        execution_log.record(action, observation)
        accumulated_results.append(observation)
        
        # Check stop conditions
        if SuccessCriteriaMet(task, accumulated_results):
            break
        if StructuralIssueDiscovered(observation):
            break
        if CannotProceed(observation):
            break
        if BlockedByFutureTask(observation, roadmap):
            return TaskResult(status=BLOCKED, explanation=observation.reason)
    
    # Generate final task result
    return TaskResult(
        status=COMPLETED,
        output=CompileOutput(accumulated_results),
        execution_log=execution_log
    )
```

---

## Algorithm 6: Result Reviewer

```python
def ResultReviewer(
    task: Task,
    result: TaskResult,
    execution_log: ExecutionLog,
    roadmap: ShallowRoadmap
) -> ReviewerDecision:
    """
    Evaluate task result and decide next Worker transition.
    
    Args:
        task: Current task with success criteria
        result: Task execution result
        execution_log: Execution history
        roadmap: Shallow task list
        
    Returns:
        Decision with status and optional context updates
    """
    # Sanity check (deterministic pre-pass)
    if not SanityCheckResult(result):
        return ReviewerDecision(
            status=NEEDS_REVISION,
            rationale="Schema validation failed"
        )
    
    # Semantic review against success criteria
    review = SemanticReview(task, result, execution_log)
    
    # Decision routing
    if review.approved:
        # Consolidate context for future tasks
        context_updates = ConsolidateContext(task, result, roadmap)
        
        return ReviewerDecision(
            status=APPROVED,
            context_updates=context_updates,
            evidence=review.evidence
        )
    
    elif review.needs_revision:
        return ReviewerDecision(
            status=NEEDS_REVISION,
            rationale=review.rationale,
            failure_context=review.failure_context
        )
    
    elif review.replan_needed:
        return ReviewerDecision(
            status=REPLAN,
            rationale=review.rationale
        )
    
    else:
        return ReviewerDecision(
            status=REJECTED,
            rationale=review.rationale
        )
```

---

## Algorithm 7: Task Analyzer (Stateless ReAct Agent)

```python
def TaskAnalyzer(input_data: Union[DigestedInformation, TaskContext, str], 
                 rationale: Optional[str] = None) -> List[Task]:
    """
    Stateless agent that produces a sequential task list from input.
    
    Args:
        input_data: Context to analyze (digest, task context, or rationale)
        rationale: Optional rationale for replanning
        
    Returns:
        List of tasks (may be nested)
    """
    # Analyze input and generate task list
    tasks = AnalyzeAndDecompose(input_data, rationale)
    
    # Ensure sequential roadmap structure
    ValidateSequentialStructure(tasks)
    
    return tasks
```

---

## Algorithm 8: Context Propagation

```python
def PropagateContext(task_tree: TaskTree, approved_task: Task, 
                    review: ReviewerDecision) -> None:
    """
    Update future task contexts based on approved results.
    
    Args:
        task_tree: Current task tree
        approved_task: Task that was approved
        review: Review decision with context updates
    """
    # Get all unfinished and upcoming tasks
    future_tasks = GetFutureTasks(task_tree, approved_task)
    
    # Apply targeted context updates
    for update in review.context_updates:
        target_task = FindTargetTask(task_tree, update.target_task_id)
        if target_task:
            UpdateTaskContext(target_task, update)
```

---

## Algorithm 9: Result Aggregation

```python
def ResultAggregationNode(task_tree: TaskTree) -> AggregatedResult:
    """
    Collect accepted task results into response-ready context.
    
    Args:
        task_tree: Completed task tree with accepted results
        
    Returns:
        Aggregated results for response synthesis
    """
    # Collect all approved results
    approved_results = CollectApprovedResults(task_tree)
    
    # Structure for response generation
    aggregated = StructureForResponse(approved_results)
    
    return aggregated
```

---

## Compact Plain-Text Reference

```text
TinyCUA(q, C, effort):
    q_enhanced, route = QueryAnalyst(q, C)
    if route == passthrough:
        return ResponseNode(q_enhanced, C)
    
    digest = InformationDigester(q_enhanced, C)
    worker_route = WorkerRoute(digest)
    
    if worker_route == passthrough:
        return ResponseNode(digest, C)
    if worker_route == task_creation:
        task_tree = CreateTaskTree(digest, effort)
    if worker_route in {task_recreation, task_reanalysis}:
        task_tree = TaskAnalyzer(digest, task_tree)
    
    while task_tree has unfinished leaf tasks:
        task = SelectNextUnfinishedLeaf(task_tree)
        result = TaskExecutor(task, ShallowRoadmap(task_tree))
        review = ResultReviewer(task, result, ExecutionLog(task), ShallowRoadmap(task_tree))
        
        if review.status == approved:
            PropagateContext(task_tree, task, review)
            MarkAccepted(task_tree, task, result, review)
        else if review.status in {needs_revision, rejected}:
            RecordFailureContext(task, review)
        else if review.status == replan:
            subtasks = TaskAnalyzer(task.context, review.rationale)
            ReplaceLeafWithSubtasks(task_tree, task, subtasks)
    
    aggregate = ResultAggregationNode(task_tree)
    return ResponseNode(aggregate)

CreateTaskTree(digest, effort):
    task_tree = TaskAnalyzer(digest)
    pass_limit = AnalysisEffortNode(effort)
    for pass in 1..pass_limit:
        selected = TaskAssessor(task_tree)
        if selected is empty:
            break
        for task in selected:
            children = TaskAnalyzer(task.context)
            AttachChildren(task_tree, task, children)
    return task_tree
```

---

## Key Design Principles

1. **Context Decomposition:** Work decomposition is a means to context decomposition. Each internal agent receives only the context needed for its responsibility.

2. **Sequential Execution:** The Worker is a sequential roadmap executor, not a parallel scheduler. Parallelization belongs inside individual task execution.

3. **Stateful Recovery:** The Result Reviewer uses structured recovery budgets (per-method budgets, no-progress guard, same-error guard) instead of simple retry counts.

4. **Targeted Propagation:** Context updates are targeted to specific future tasks, not dumped into all future contexts.

5. **Hybrid Review:** Deterministic checks validate schema and structure before LLM-based semantic review evaluates correctness and sufficiency.

---

## Component Reference

| Component | Type | Role |
|-----------|------|------|
| Query Analyst | Agent | Fast high-level scan + classification |
| Information Digester | Agent | Precision-oriented context exploration |
| Task Creation | Process | Upfront decomposition loop |
| Task Assessor | Agent | Selects tasks for decomposition |
| Task Analyzer | Agent | Stateless task list generation |
| Task Executor | Agent | ReAct execution of one task |
| Result Reviewer | Agent | Hybrid review + decision routing |
| Primary Agent | Agent | Final response composition |

---

## Notes for Manuscript Text

- The Query Analyst is a routing node that decides whether a request should pass through to response synthesis or enter Worker mode.

- The Information Digester is a context-narrowing node that gathers and condenses relevant context before Worker planning begins.

- The Worker is a sequential controller that executes one unfinished leaf task at a time.

- Task Creation builds the initial task tree by alternating Task Analyzer and Task Assessor passes according to the configured effort level.

- The Task Executor performs the concrete work for one leaf task using task-scoped context and shallow roadmap awareness.

- The Result Reviewer gates progress: accepted results update future task context; rejected or revision-needed results return to execution; replan decisions invoke the Task Analyzer to replace the current leaf with subtasks.

- Result Aggregation collects accepted task results into response-ready context, and ResponseNode produces the final user-facing answer.
