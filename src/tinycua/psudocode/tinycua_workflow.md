# TINYCUA Workflow Pseudocode

> **Purpose:** Algorithmic explanation of the TINYCUA main workflow.

---

**Algorithm 1:** Pseudocode of main workflow for TINYCUA

**Function:** $`\texttt{TinyCUA(q, C, effort)}`$

**Input:**
- User query $q$
- Session context $C$ ($\texttt{chat\_history} + \texttt{context}$)
- Worker effort configuration $\texttt{effort}$

**Output:**
- Final user response $r$

---

Initialize $q_\texttt{enhanced}$ and $\texttt{route}$

**Step 1:** *Query Analyst — High-level context scan*

$q_\texttt{enhanced}, \texttt{route} \leftarrow \texttt{QueryAnalyst(q, C)}$

**if** $\texttt{route} = \texttt{PASSTHROUGH}$ **then**

$\quad r \leftarrow \texttt{ResponseNode}(q_\texttt{enhanced}, C)$

$\quad$ **return** $r$

**end if**

---

**Step 2:** *Information Digester — Context condensation*

$d \leftarrow \texttt{InformationDigester}(q_\texttt{enhanced}, C)$

$\texttt{worker\_route} \leftarrow \texttt{WorkerRoute}(d)$

**if** $\texttt{worker\_route} = \texttt{PASSTHROUGH}$ **then**

$\quad r \leftarrow \texttt{ResponseNode}(d, C)$

$\quad$ **return** $r$

**end if**

---

**Step 3:** *Task Tree Creation*

**if** $\texttt{worker\_route} = \texttt{TASK\_CREATION}$ **then**

$\quad T \leftarrow \texttt{CreateTaskTree}(d, \texttt{effort})$

**else if** $\texttt{worker\_route} \in \{\texttt{TASK\_RECREATION}, \texttt{TASK\_REANALYSIS}\}$ **then**

$\quad T \leftarrow \texttt{TaskAnalyzer}(d, T)$

**end if**

---

**Step 4:** *Sequential Task Execution*

**while** $\exists$ unfinished leaf task $t$ in $T$ **do**

$\quad$ *Step 4.1: Select next task*

$\quad t \leftarrow \texttt{SelectNextUnfinishedLeaf}(T)$

$\quad$ *Step 4.2: Execute task*

$\quad y \leftarrow \texttt{TaskExecutor}(t, \texttt{ShallowRoadmap}(T))$

$\quad$ *Step 4.3: Review result*

$\quad v \leftarrow \texttt{ResultReviewer}(t, y, \texttt{ExecutionLog}(t), \texttt{ShallowRoadmap}(T))$

$\quad$ *Step 4.4: Handle review decision*

$\quad$ **if** $v.\texttt{status} = \texttt{APPROVED}$ **then**

$\quad\quad \texttt{PropagateContext}(T, t, v)$

$\quad\quad \texttt{MarkAccepted}(T, t, y, v)$

$\quad$ **else if** $v.\texttt{status} \in \{\texttt{NEEDS\_REVISION}, \texttt{REJECTED}\}$ **then**

$\quad\quad \texttt{RecordFailureContext}(t, v)$

$\quad$ **else if** $v.\texttt{status} = \texttt{REPLAN}$ **then**

$\quad\quad S \leftarrow \texttt{TaskAnalyzer}(t.\texttt{context}, v.\texttt{rationale})$

$\quad\quad \texttt{ReplaceLeafWithSubtasks}(T, t, S)$

$\quad$ **end if**

**end while**

---

**Step 5:** *Result Aggregation and Response*

$a \leftarrow \texttt{ResultAggregationNode}(T)$

$r \leftarrow \texttt{ResponseNode}(a)$

**return** $r$

---

**Algorithm 2:** Pseudocode of task tree creation

**Function:** $`\texttt{CreateTaskTree(d, effort)}`$

**Input:**
- Digested information $d$
- Worker effort $\texttt{effort}$

**Output:**
- Sequential task tree $T$

---

$T \leftarrow \texttt{TaskAnalyzer}(d)$

$p_\max \leftarrow \texttt{AnalysisEffortNode}(\texttt{effort})$

**for** $p = 1$ **to** $p_\max$ **do**

$\quad S \leftarrow \texttt{TaskAssessor}(T)$

$\quad$ **if** $S = \emptyset$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

$\quad$ **for each** task $t \in S$ **do**

$\quad\quad c \leftarrow \texttt{TaskAnalyzer}(t.\texttt{context})$

$\quad\quad \texttt{AttachChildren}(T, t, c)$

$\quad$ **end for**

**end for**

**return** $T$

---

**Algorithm 3:** Pseudocode of query analyst

**Function:** $`\texttt{QueryAnalyst(q, C)}`$

**Input:**
- User query $q$
- Session context $C$

**Output:**
- Context Enhanced Query $q_\texttt{enhanced}$
- Classification $\texttt{route}$

---

$q_\texttt{enhanced} \leftarrow \texttt{EnhanceQuery}(q, C.\texttt{chat\_history}, C.\texttt{context})$

$\texttt{route} \leftarrow \texttt{ClassifyRequest}(q_\texttt{enhanced})$

$\texttt{ValidateClassification}(\texttt{route})$

**return** $q_\texttt{enhanced}, \texttt{route}$

---

**Algorithm 4:** Pseudocode of information digester

**Function:** $`\texttt{InformationDigester(ceq, C)}`$

**Input:**
- Context Enhanced Query $\texttt{ceq}$
- Session context $C$

**Output:**
- Digested information $d$

---

$g \leftarrow \texttt{IdentifyInformationGaps}(\texttt{ceq})$

$r \leftarrow \texttt{EnhancedContextRetrieval}(g, C.\texttt{context})$

$t \leftarrow \texttt{IdentifyRelevantTopics}(r)$

$e \leftarrow \texttt{ExtractRelevantContext}(r, t)$

$f \leftarrow \texttt{RemoveDistractingContext}(e)$

$p \leftarrow \texttt{PreserveTaskCriticalDetails}(f)$

$d \leftarrow \texttt{StructureDigest}(p)$

**return** $d$

---

**Algorithm 5:** Pseudocode of task executor

**Function:** $`\texttt{TaskExecutor(task, roadmap)}`$

**Input:**
- Current task $\texttt{task}$ with context and success criteria
- Shallow roadmap $\texttt{roadmap}$

**Output:**
- Task result $\texttt{result}$

---

$log \leftarrow \texttt{ExecutionLog}()$

$results \leftarrow []$

**while** true **do**

$\quad$ *Think: Plan action*

$\quad a \leftarrow \texttt{Think}(\texttt{task}, results, \texttt{roadmap})$

$\quad$ *Act: Execute tool or reasoning*

$\quad o \leftarrow \texttt{Act}(a, \texttt{task}.\texttt{context})$

$\quad$ *Observe: Record result*

$\quad \texttt{log.record}(a, o)$

$\quad \texttt{results.append}(o)$

$\quad$ *Check stop conditions*

$\quad$ **if** $\texttt{SuccessCriteriaMet}(\texttt{task}, results)$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

$\quad$ **if** $\texttt{CannotProceed}(o)$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

**end while**

$\texttt{result} \leftarrow \texttt{TaskResult}(\texttt{COMPILE}(results), log)$

**return** $\texttt{result}$

---

**Algorithm 6:** Pseudocode of result reviewer

**Function:** $`\texttt{ResultReviewer(task, result, log, roadmap)}`$

**Input:**
- Current task $\texttt{task}$
- Task result $\texttt{result}$
- Execution log $\texttt{log}$
- Shallow roadmap $\texttt{roadmap}$

**Output:**
- Reviewer decision $\texttt{decision}$

---

**if** $\neg \texttt{SanityCheckResult}(\texttt{result})$ **then**

$\quad$ **return** $\texttt{Decision}(\texttt{NEEDS\_REVISION}, \text{"Schema validation failed"})$

**end if**

$rv \leftarrow \texttt{SemanticReview}(\texttt{task}, \texttt{result}, \texttt{log})$

**if** $rv.\texttt{approved}$ **then**

$\quad u \leftarrow \texttt{ConsolidateContext}(\texttt{task}, \texttt{result}, \texttt{roadmap})$

$\quad$ **return** $\texttt{Decision}(\texttt{APPROVED}, u, rv.\texttt{evidence})$

**else if** $rv.\texttt{needs\_revision}$ **then**

$\quad$ **return** $\texttt{Decision}(\texttt{NEEDS\_REVISION}, rv.\texttt{rationale})$

**else if** $rv.\texttt{replan\_needed}$ **then**

$\quad$ **return** $\texttt{Decision}(\texttt{REPLAN}, rv.\texttt{rationale})$

**else**

$\quad$ **return** $\texttt{Decision}(\texttt{REJECTED}, rv.\texttt{rationale})$

**end if**

---

**Algorithm 7:** Pseudocode of task analyzer

**Function:** $`\texttt{TaskAnalyzer(input\_data, rationale)}`$

**Input:**
- Input data $\texttt{input\_data}$ (digest, task context, or rationale)
- Optional rationale $\texttt{rationale}$

**Output:**
- List of tasks $T$

---

$T \leftarrow \texttt{AnalyzeAndDecompose}(\texttt{input\_data}, \texttt{rationale})$

$\texttt{ValidateSequentialStructure}(T)$

**return** $T$

---

**Algorithm 8:** Pseudocode of context propagation

**Function:** $`\texttt{PropagateContext(T, approved\_task, review)}`$

**Input:**
- Task tree $T$
- Approved task $\texttt{approved\_task}$
- Review decision $\texttt{review}$

**Output:**
- Updated task tree $T$

---

$f \leftarrow \texttt{GetFutureTasks}(T, \texttt{approved\_task})$

**for each** $u \in \texttt{review}.\texttt{context\_updates}$ **do**

$\quad tgt \leftarrow \texttt{FindTargetTask}(T, u.\texttt{target\_task\_id})$

$\quad$ **if** $tgt \neq \texttt{null}$ **then**

$\quad\quad \texttt{UpdateTaskContext}(tgt, u)$

$\quad$ **end if**

**end for**

---

**Algorithm 9:** Pseudocode of result aggregation

**Function:** $`\texttt{ResultAggregationNode(T)}`$

**Input:**
- Completed task tree $T$

**Output:**
- Aggregated result $\texttt{aggregate}$

---

$a \leftarrow \texttt{CollectApprovedResults}(T)$

$\texttt{aggregate} \leftarrow \texttt{StructureForResponse}(a)$

**return** $\texttt{aggregate}$

---

## Key Design Principles

1. **Context Decomposition:** Work decomposition is a means to context decomposition. Each internal agent receives only the context needed for its responsibility.

2. **Sequential Execution:** The Worker is a sequential roadmap executor, not a parallel scheduler. Parallelization belongs inside individual task execution.

3. **Stateful Recovery:** The Result Reviewer uses structured recovery budgets instead of simple retry counts.

4. **Targeted Propagation:** Context updates are targeted to specific future tasks, not dumped into all future contexts.

5. **Hybrid Review:** Deterministic checks validate schema and structure before LLM-based semantic review evaluates correctness and sufficiency.
