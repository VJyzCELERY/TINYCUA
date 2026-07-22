# TINYCUA Workflow Pseudocode

> **Purpose:** Algorithmic explanation of the TINYCUA main workflow.

---

**Algorithm 1:** Pseudocode of main workflow for TINYCUA

**Function:** $`\text{TinyCUA}(q, C, \text{effort})`$

**Input:**
- User query $q$
- Session context $C$ ($\text{chat\_history} + \text{context}$)
- Worker effort configuration $\text{effort}$

**Output:**
- Final user response $r$

---

Initialize $`q_{\text{enhanced}}`$ and $`\text{route}`$

**Step 1:** *Query Analyst — High-level context scan*

$`q_{\text{enhanced}}, \text{route} \leftarrow \text{QueryAnalyst}(q, C)`$

**if** $`\text{route} = \text{PASSTHROUGH}`$ **then**

$\quad r \leftarrow \text{ResponseNode}(q_{\text{enhanced}}, C)$

$\quad$ **return** $r$

**end if**

---

**Step 2:** *Information Digester — Context condensation*

$`d \leftarrow \text{InformationDigester}(q_{\text{enhanced}}, C)`$

$`\text{worker\_route} \leftarrow \text{WorkerRoute}(d)`$

**if** $`\text{worker\_route} = \text{PASSTHROUGH}`$ **then**

$\quad r \leftarrow \text{ResponseNode}(d, C)$

$\quad$ **return** $r$

**end if**

---

**Step 3:** *Task Tree Creation*

**if** $`\text{worker\_route} = \text{TASK\_CREATION}`$ **then**

$\quad T \leftarrow \text{CreateTaskTree}(d, \text{effort})$

**else if** $`\text{worker\_route} \in \{\text{TASK\_RECREATION}, \text{TASK\_REANALYSIS}\}`$ **then**

$\quad T \leftarrow \text{TaskAnalyzer}(d, T)$

**end if**

---

**Step 4:** *Sequential Task Execution*

**while** $`\exists`$ unfinished leaf task $t$ in $T$ **do**

$\quad$ *Step 4.1: Select next task*

$\quad t \leftarrow \text{SelectNextUnfinishedLeaf}(T)$

$\quad$ *Step 4.2: Execute task*

$\quad y \leftarrow \text{TaskExecutor}(t, \text{ShallowRoadmap}(T))$

$\quad$ *Step 4.3: Review result*

$\quad v \leftarrow \text{ResultReviewer}(t, y, \text{ExecutionLog}(t), \text{ShallowRoadmap}(T))$

$\quad$ *Step 4.4: Handle review decision*

$\quad$ **if** $`v.\text{status} = \text{APPROVED}`$ **then**

$\quad\quad \text{PropagateContext}(T, t, v)$

$\quad\quad \text{MarkAccepted}(T, t, y, v)$

$\quad$ **else if** $`v.\text{status} \in \{\text{NEEDS\_REVISION}, \text{REJECTED}\}`$ **then**

$\quad\quad \text{RecordFailureContext}(t, v)$

$\quad$ **else if** $`v.\text{status} = \text{REPLAN}`$ **then**

$\quad\quad S \leftarrow \text{TaskAnalyzer}(t.\text{context}, v.\text{rationale})$

$\quad\quad \text{ReplaceLeafWithSubtasks}(T, t, S)$

$\quad$ **end if**

**end while**

---

**Step 5:** *Result Aggregation and Response*

$`a \leftarrow \text{ResultAggregationNode}(T)`$

$`r \leftarrow \text{ResponseNode}(a)`$

**return** $r$

---

**Algorithm 2:** Pseudocode of task tree creation

**Function:** $`\text{CreateTaskTree}(d, \text{effort})`$

**Input:**
- Digested information $d$
- Worker effort $\text{effort}$

**Output:**
- Sequential task tree $T$

---

$`T \leftarrow \text{TaskAnalyzer}(d)`$

$`p_{\max} \leftarrow \text{AnalysisEffortNode}(\text{effort})`$

**for** $`p = 1`$ **to** $`p_{\max}`$ **do**

$\quad S \leftarrow \text{TaskAssessor}(T)$

$\quad$ **if** $`S = \emptyset`$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

$\quad$ **for each** task $t \in S$ **do**

$\quad\quad c \leftarrow \text{TaskAnalyzer}(t.\text{context})$

$\quad\quad \text{AttachChildren}(T, t, c)$

$\quad$ **end for**

**end for**

**return** $T$

---

**Algorithm 3:** Pseudocode of query analyst

**Function:** $`\text{QueryAnalyst}(q, C)`$

**Input:**
- User query $q$
- Session context $C$

**Output:**
- Context Enhanced Query $q_{\text{enhanced}}$
- Classification $\text{route}$

---

$`q_{\text{enhanced}} \leftarrow \text{EnhanceQuery}(q, C.\text{chat\_history}, C.\text{context})`$

$`\text{route} \leftarrow \text{ClassifyRequest}(q_{\text{enhanced}})`$

$`\text{ValidateClassification}(\text{route})`$

**return** $q_{\text{enhanced}}, \text{route}$

---

**Algorithm 4:** Pseudocode of information digester

**Function:** $`\text{InformationDigester}(\text{ceq}, C)`$

**Input:**
- Context Enhanced Query $\text{ceq}$
- Session context $C$

**Output:**
- Digested information $d$

---

$`g \leftarrow \text{IdentifyInformationGaps}(\text{ceq})`$

$`r \leftarrow \text{EnhancedContextRetrieval}(g, C.\text{context})`$

$`t \leftarrow \text{IdentifyRelevantTopics}(r)`$

$`e \leftarrow \text{ExtractRelevantContext}(r, t)`$

$`f \leftarrow \text{RemoveDistractingContext}(e)`$

$`p \leftarrow \text{PreserveTaskCriticalDetails}(f)`$

$`d \leftarrow \text{StructureDigest}(p)`$

**return** $d$

---

**Algorithm 5:** Pseudocode of task executor

**Function:** $`\text{TaskExecutor}(\text{task}, \text{roadmap})`$

**Input:**
- Current task $\text{task}$ with context and success criteria
- Shallow roadmap $\text{roadmap}$

**Output:**
- Task result $\text{result}$

---

$`\log \leftarrow \text{ExecutionLog}()`$

$`\text{results} \leftarrow []`$

**while** true **do**

$\quad$ *Think: Plan action*

$\quad a \leftarrow \text{Think}(\text{task}, \text{results}, \text{roadmap})$

$\quad$ *Act: Execute tool or reasoning*

$\quad o \leftarrow \text{Act}(a, \text{task}.\text{context})$

$\quad$ *Observe: Record result*

$\quad \log.\text{record}(a, o)$

$\quad \text{results}.\text{append}(o)$

$\quad$ *Check stop conditions*

$\quad$ **if** $`\text{SuccessCriteriaMet}(\text{task}, \text{results})`$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

$\quad$ **if** $`\text{CannotProceed}(o)`$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

**end while**

$`\text{result} \leftarrow \text{TaskResult}(\text{COMPILE}(\text{results}), \log)`$

**return** $\text{result}$

---

**Algorithm 6:** Pseudocode of result reviewer

**Function:** $`\text{ResultReviewer}(\text{task}, \text{result}, \log, \text{roadmap})`$

**Input:**
- Current task $\text{task}$
- Task result $\text{result}$
- Execution log $\log$
- Shallow roadmap $\text{roadmap}$

**Output:**
- Reviewer decision $\text{decision}$

---

**if** $`\neg \text{SanityCheckResult}(\text{result})`$ **then**

$\quad$ **return** $`\text{Decision}(\text{NEEDS\_REVISION}, \text{"Schema validation failed"})`$

**end if**

$`rv \leftarrow \text{SemanticReview}(\text{task}, \text{result}, \log)`$

**if** $`rv.\text{approved}$ **then**

$\quad u \leftarrow \text{ConsolidateContext}(\text{task}, \text{result}, \text{roadmap})$

$\quad$ **return** $`\text{Decision}(\text{APPROVED}, u, rv.\text{evidence})`$

**else if** $`rv.\text{needs\_revision}`$ **then**

$\quad$ **return** $`\text{Decision}(\text{NEEDS\_REVISION}, rv.\text{rationale})`$

**else if** $`rv.\text{replan\_needed}`$ **then**

$\quad$ **return** $`\text{Decision}(\text{REPLAN}, rv.\text{rationale})`$

**else**

$\quad$ **return** $`\text{Decision}(\text{REJECTED}, rv.\text{rationale})`$

**end if**

---

**Algorithm 7:** Pseudocode of task analyzer

**Function:** $`\text{TaskAnalyzer}(\text{input\_data}, \text{rationale})`$

**Input:**
- Input data $\text{input\_data}$ (digest, task context, or rationale)
- Optional rationale $\text{rationale}$

**Output:**
- List of tasks $T$

---

$`T \leftarrow \text{AnalyzeAndDecompose}(\text{input\_data}, \text{rationale})`$

$`\text{ValidateSequentialStructure}(T)`$

**return** $T$

---

**Algorithm 8:** Pseudocode of context propagation

**Function:** $`\text{PropagateContext}(T, \text{approved\_task}, \text{review})`$

**Input:**
- Task tree $T$
- Approved task $\text{approved\_task}$
- Review decision $\text{review}$

**Output:**
- Updated task tree $T$

---

$`f \leftarrow \text{GetFutureTasks}(T, \text{approved\_task})`$

**for each** $`u \in \text{review}.\text{context\_updates}`$ **do**

$\quad tgt \leftarrow \text{FindTargetTask}(T, u.\text{target\_task\_id})$

$\quad$ **if** $`tgt \neq \text{null}`$ **then**

$\quad\quad \text{UpdateTaskContext}(tgt, u)$

$\quad$ **end if**

**end for**

---

**Algorithm 9:** Pseudocode of result aggregation

**Function:** $`\text{ResultAggregationNode}(T)`$

**Input:**
- Completed task tree $T$

**Output:**
- Aggregated result $\text{aggregate}$

---

$`a \leftarrow \text{CollectApprovedResults}(T)`$

$`\text{aggregate} \leftarrow \text{StructureForResponse}(a)`$

**return** $\text{aggregate}$

---

## Key Design Principles

1. **Context Decomposition:** Work decomposition is a means to context decomposition. Each internal agent receives only the context needed for its responsibility.

2. **Sequential Execution:** The Worker is a sequential roadmap executor, not a parallel scheduler. Parallelization belongs inside individual task execution.

3. **Stateful Recovery:** The Result Reviewer uses structured recovery budgets instead of simple retry counts.

4. **Targeted Propagation:** Context updates are targeted to specific future tasks, not dumped into all future contexts.

5. **Hybrid Review:** Deterministic checks validate schema and structure before LLM-based semantic review evaluates correctness and sufficiency.
