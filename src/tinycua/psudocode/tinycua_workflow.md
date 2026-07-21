# TINYCUA Workflow Pseudocode

> **Purpose:** Algorithmic explanation of the TINYCUA main workflow.

---

**Algorithm 1:** Pseudocode of main workflow for TINYCUA

**Function:** `TinyCUA(q, C, effort)`

**Input:**
- User query $q$
- Session context $C$ (chat_history + context)
- Worker effort configuration $effort$

**Output:**
- Final user response $r$

---

Initialize $q_{enhanced}$ and $route$

**Step 1:** *Query Analyst — High-level context scan*

$q_{enhanced}, route \leftarrow \text{QueryAnalyst}(q, C)$

**if** $route = \text{PASSTHROUGH}$ **then**

$\quad r \leftarrow \text{ResponseNode}(q_{enhanced}, C)$

$\quad$ **return** $r$

**end if**

---

**Step 2:** *Information Digester — Context condensation*

$digest \leftarrow \text{InformationDigester}(q_{enhanced}, C)$

$worker\_route \leftarrow \text{WorkerRoute}(digest)$

**if** $worker\_route = \text{PASSTHROUGH}$ **then**

$\quad r \leftarrow \text{ResponseNode}(digest, C)$

$\quad$ **return** $r$

**end if**

---

**Step 3:** *Task Tree Creation*

**if** $worker\_route = \text{TASK\_CREATION}$ **then**

$\quad T \leftarrow \text{CreateTaskTree}(digest, effort)$

**else if** $worker\_route \in \{\text{TASK\_RECREATION}, \text{TASK\_REANALYSIS}\}$ **then**

$\quad T \leftarrow \text{TaskAnalyzer}(digest, T)$

**end if**

---

**Step 4:** *Sequential Task Execution*

**while** $\exists$ unfinished leaf task $t$ in $T$ **do**

$\quad$ *Step 4.1: Select next task*

$\quad t \leftarrow \text{SelectNextUnfinishedLeaf}(T)$

$\quad$ *Step 4.2: Execute task*

$\quad y \leftarrow \text{TaskExecutor}(t, \text{ShallowRoadmap}(T))$

$\quad$ *Step 4.3: Review result*

$\quad v \leftarrow \text{ResultReviewer}(t, y, \text{ExecutionLog}(t), \text{ShallowRoadmap}(T))$

$\quad$ *Step 4.4: Handle review decision*

$\quad$ **if** $v.status = \text{APPROVED}$ **then**

$\quad\quad \text{PropagateContext}(T, t, v)$

$\quad\quad \text{MarkAccepted}(T, t, y, v)$

$\quad$ **else if** $v.status \in \{\text{NEEDS\_REVISION}, \text{REJECTED}\}$ **then**

$\quad\quad \text{RecordFailureContext}(t, v)$

$\quad$ **else if** $v.status = \text{REPLAN}$ **then**

$\quad\quad S \leftarrow \text{TaskAnalyzer}(t.context, v.rationale)$

$\quad\quad \text{ReplaceLeafWithSubtasks}(T, t, S)$

$\quad$ **end if**

**end while**

---

**Step 5:** *Result Aggregation and Response*

$a \leftarrow \text{ResultAggregationNode}(T)$

$r \leftarrow \text{ResponseNode}(a)$

**return** $r$

---

**Algorithm 2:** Pseudocode of task tree creation

**Function:** `CreateTaskTree(digest, effort)`

**Input:**
- Digested information $digest$
- Worker effort $effort$

**Output:**
- Sequential task tree $T$

---

$T \leftarrow \text{TaskAnalyzer}(digest)$

$p_{max} \leftarrow \text{AnalysisEffortNode}(effort)$

**for** $p = 1$ **to** $p_{max}$ **do**

$\quad S \leftarrow \text{TaskAssessor}(T)$

$\quad$ **if** $S = \emptyset$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

$\quad$ **for each** task $t \in S$ **do**

$\quad\quad children \leftarrow \text{TaskAnalyzer}(t.context)$

$\quad\quad \text{AttachChildren}(T, t, children)$

$\quad$ **end for**

**end for**

**return** $T$

---

**Algorithm 3:** Pseudocode of query analyst

**Function:** `QueryAnalyst(q, C)`

**Input:**
- User query $q$
- Session context $C$

**Output:**
- Context Enhanced Query $q_{enhanced}$
- Classification $route$

---

$q_{enhanced} \leftarrow \text{EnhanceQuery}(q, C.chat\_history, C.context)$

$route \leftarrow \text{ClassifyRequest}(q_{enhanced})$

$\text{ValidateClassification}(route)$

**return** $q_{enhanced}, route$

---

**Algorithm 4:** Pseudocode of information digester

**Function:** `InformationDigester(ceq, C)`

**Input:**
- Context Enhanced Query $ceq$
- Session context $C$

**Output:**
- Digested information $digest$

---

$gaps \leftarrow \text{IdentifyInformationGaps}(ceq)$

$retrieved \leftarrow \text{EnhancedContextRetrieval}(gaps, C.context)$

$topics \leftarrow \text{IdentifyRelevantTopics}(retrieved)$

$extracted \leftarrow \text{ExtractRelevantContext}(retrieved, topics)$

$filtered \leftarrow \text{RemoveDistractingContext}(extracted)$

$preserved \leftarrow \text{PreserveTaskCriticalDetails}(filtered)$

$digest \leftarrow \text{StructureDigest}(preserved)$

**return** $digest$

---

**Algorithm 5:** Pseudocode of task executor

**Function:** `TaskExecutor(task, roadmap)`

**Input:**
- Current task $task$ with context and success criteria
- Shallow roadmap $roadmap$

**Output:**
- Task result $result$

---

$log \leftarrow \text{ExecutionLog}()$

$results \leftarrow []$

**while** true **do**

$\quad$ *Think: Plan action*

$\quad action \leftarrow \text{Think}(task, results, roadmap)$

$\quad$ *Act: Execute tool or reasoning*

$\quad observation \leftarrow \text{Act}(action, task.context)$

$\quad$ *Observe: Record result*

$\quad \log.\text{record}(action, observation)$

$\quad results.\text{append}(observation)$

$\quad$ *Check stop conditions*

$\quad$ **if** $\text{SuccessCriteriaMet}(task, results)$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

$\quad$ **if** $\text{CannotProceed}(observation)$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

**end while**

$result \leftarrow \text{TaskResult}(\text{COMPILE}(results), log)$

**return** $result$

---

**Algorithm 6:** Pseudocode of result reviewer

**Function:** `ResultReviewer(task, result, log, roadmap)`

**Input:**
- Current task $task$
- Task result $result$
- Execution log $log$
- Shallow roadmap $roadmap$

**Output:**
- Reviewer decision $decision$

---

**if** $\neg \text{SanityCheckResult}(result)$ **then**

$\quad$ **return** $\text{Decision}(\text{NEEDS\_REVISION}, \text{"Schema validation failed"})$

**end if**

$review \leftarrow \text{SemanticReview}(task, result, log)$

**if** $review.approved$ **then**

$\quad updates \leftarrow \text{ConsolidateContext}(task, result, roadmap)$

$\quad$ **return** $\text{Decision}(\text{APPROVED}, updates, review.evidence)$

**else if** $review.needs\_revision$ **then**

$\quad$ **return** $\text{Decision}(\text{NEEDS\_REVISION}, review.rationale)$

**else if** $review.replan\_needed$ **then**

$\quad$ **return** $\text{Decision}(\text{REPLAN}, review.rationale)$

**else**

$\quad$ **return** $\text{Decision}(\text{REJECTED}, review.rationale)$

**end if**

---

**Algorithm 7:** Pseudocode of task analyzer

**Function:** `TaskAnalyzer(input_data, rationale)`

**Input:**
- Input data $input\_data$ (digest, task context, or rationale)
- Optional rationale $rationale$

**Output:**
- List of tasks $T$

---

$T \leftarrow \text{AnalyzeAndDecompose}(input\_data, rationale)$

$\text{ValidateSequentialStructure}(T)$

**return** $T$

---

**Algorithm 8:** Pseudocode of context propagation

**Function:** `PropagateContext(T, approved_task, review)`

**Input:**
- Task tree $T$
- Approved task $approved\_task$
- Review decision $review$

**Output:**
- Updated task tree $T$

---

$future \leftarrow \text{GetFutureTasks}(T, approved\_task)$

**for each** $update \in review.context\_updates$ **do**

$\quad target \leftarrow \text{FindTargetTask}(T, update.target\_task\_id)$

$\quad$ **if** $target \neq \text{null}$ **then**

$\quad\quad \text{UpdateTaskContext}(target, update)$

$\quad$ **end if**

**end for**

---

**Algorithm 9:** Pseudocode of result aggregation

**Function:** `ResultAggregationNode(T)`

**Input:**
- Completed task tree $T$

**Output:**
- Aggregated result $aggregate$

---

$approved \leftarrow \text{CollectApprovedResults}(T)$

$aggregate \leftarrow \text{StructureForResponse}(approved)$

**return** $aggregate$

---

## Key Design Principles

1. **Context Decomposition:** Work decomposition is a means to context decomposition. Each internal agent receives only the context needed for its responsibility.

2. **Sequential Execution:** The Worker is a sequential roadmap executor, not a parallel scheduler. Parallelization belongs inside individual task execution.

3. **Stateful Recovery:** The Result Reviewer uses structured recovery budgets instead of simple retry counts.

4. **Targeted Propagation:** Context updates are targeted to specific future tasks, not dumped into all future contexts.

5. **Hybrid Review:** Deterministic checks validate schema and structure before LLM-based semantic review evaluates correctness and sufficiency.
