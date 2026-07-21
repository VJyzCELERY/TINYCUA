# TINYCUA Workflow Pseudocode

> **Purpose:** Algorithmic explanation of the TINYCUA main workflow.

---

**Algorithm 1:** Pseudocode of main workflow for TINYCUA

**Function:** $\text{TinyCUA}(q, C, \text{effort})$

**Input:**
- User query $q$
- Session context $C$ ($\text{chat\_history} + \text{context}$)
- Worker effort configuration $\text{effort}$

**Output:**
- Final user response $r$

---

Initialize $q_{\text{enhanced}}$ and $\text{route}$

**Step 1:** *Query Analyst — High-level context scan*

$q_{\text{enhanced}}, \text{route} \leftarrow \text{QueryAnalyst}(q, C)$

**if** $\text{route} = \text{PASSTHROUGH}$ **then**

$\quad r \leftarrow \text{ResponseNode}(q_{\text{enhanced}}, C)$

$\quad$ **return** $r$

**end if**

---

**Step 2:** *Information Digester — Context condensation*

$\text{digest} \leftarrow \text{InformationDigester}(q_{\text{enhanced}}, C)$

$\text{worker\_route} \leftarrow \text{WorkerRoute}(\text{digest})$

**if** $\text{worker\_route} = \text{PASSTHROUGH}$ **then**

$\quad r \leftarrow \text{ResponseNode}(\text{digest}, C)$

$\quad$ **return** $r$

**end if**

---

**Step 3:** *Task Tree Creation*

**if** $\text{worker\_route} = \text{TASK\_CREATION}$ **then**

$\quad T \leftarrow \text{CreateTaskTree}(\text{digest}, \text{effort})$

**else if** $\text{worker\_route} \in \{\text{TASK\_RECREATION}, \text{TASK\_REANALYSIS}\}$ **then**

$\quad T \leftarrow \text{TaskAnalyzer}(\text{digest}, T)$

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

$\quad$ **if** $v.\text{status} = \text{APPROVED}$ **then**

$\quad\quad \text{PropagateContext}(T, t, v)$

$\quad\quad \text{MarkAccepted}(T, t, y, v)$

$\quad$ **else if** $v.\text{status} \in \{\text{NEEDS\_REVISION}, \text{REJECTED}\}$ **then**

$\quad\quad \text{RecordFailureContext}(t, v)$

$\quad$ **else if** $v.\text{status} = \text{REPLAN}$ **then**

$\quad\quad S \leftarrow \text{TaskAnalyzer}(t.\text{context}, v.\text{rationale})$

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

**Function:** $\text{CreateTaskTree}(\text{digest}, \text{effort})$

**Input:**
- Digested information $\text{digest}$
- Worker effort $\text{effort}$

**Output:**
- Sequential task tree $T$

---

$T \leftarrow \text{TaskAnalyzer}(\text{digest})$

$p_{\max} \leftarrow \text{AnalysisEffortNode}(\text{effort})$

**for** $p = 1$ **to** $p_{\max}$ **do**

$\quad S \leftarrow \text{TaskAssessor}(T)$

$\quad$ **if** $S = \emptyset$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

$\quad$ **for each** task $t \in S$ **do**

$\quad\quad \text{children} \leftarrow \text{TaskAnalyzer}(t.\text{context})$

$\quad\quad \text{AttachChildren}(T, t, \text{children})$

$\quad$ **end for**

**end for**

**return** $T$

---

**Algorithm 3:** Pseudocode of query analyst

**Function:** $\text{QueryAnalyst}(q, C)$

**Input:**
- User query $q$
- Session context $C$

**Output:**
- Context Enhanced Query $q_{\text{enhanced}}$
- Classification $\text{route}$

---

$q_{\text{enhanced}} \leftarrow \text{EnhanceQuery}(q, C.\text{chat\_history}, C.\text{context})$

$\text{route} \leftarrow \text{ClassifyRequest}(q_{\text{enhanced}})$

$\text{ValidateClassification}(\text{route})$

**return** $q_{\text{enhanced}}, \text{route}$

---

**Algorithm 4:** Pseudocode of information digester

**Function:** $\text{InformationDigester}(\text{ceq}, C)$

**Input:**
- Context Enhanced Query $\text{ceq}$
- Session context $C$

**Output:**
- Digested information $\text{digest}$

---

$\text{gaps} \leftarrow \text{IdentifyInformationGaps}(\text{ceq})$

$\text{retrieved} \leftarrow \text{EnhancedContextRetrieval}(\text{gaps}, C.\text{context})$

$\text{topics} \leftarrow \text{IdentifyRelevantTopics}(\text{retrieved})$

$\text{extracted} \leftarrow \text{ExtractRelevantContext}(\text{retrieved}, \text{topics})$

$\text{filtered} \leftarrow \text{RemoveDistractingContext}(\text{extracted})$

$\text{preserved} \leftarrow \text{PreserveTaskCriticalDetails}(\text{filtered})$

$\text{digest} \leftarrow \text{StructureDigest}(\text{preserved})$

**return** $\text{digest}$

---

**Algorithm 5:** Pseudocode of task executor

**Function:** $\text{TaskExecutor}(\text{task}, \text{roadmap})$

**Input:**
- Current task $\text{task}$ with context and success criteria
- Shallow roadmap $\text{roadmap}$

**Output:**
- Task result $\text{result}$

---

$\text{log} \leftarrow \text{ExecutionLog}()$

$\text{results} \leftarrow []$

**while** true **do**

$\quad$ *Think: Plan action*

$\quad \text{action} \leftarrow \text{Think}(\text{task}, \text{results}, \text{roadmap})$

$\quad$ *Act: Execute tool or reasoning*

$\quad \text{observation} \leftarrow \text{Act}(\text{action}, \text{task}.\text{context})$

$\quad$ *Observe: Record result*

$\quad \text{log}.\text{record}(\text{action}, \text{observation})$

$\quad \text{results}.\text{append}(\text{observation})$

$\quad$ *Check stop conditions*

$\quad$ **if** $\text{SuccessCriteriaMet}(\text{task}, \text{results})$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

$\quad$ **if** $\text{CannotProceed}(\text{observation})$ **then**

$\quad\quad$ **break**

$\quad$ **end if**

**end while**

$\text{result} \leftarrow \text{TaskResult}(\text{COMPILE}(\text{results}), \text{log})$

**return** $\text{result}$

---

**Algorithm 6:** Pseudocode of result reviewer

**Function:** $\text{ResultReviewer}(\text{task}, \text{result}, \text{log}, \text{roadmap})$

**Input:**
- Current task $\text{task}$
- Task result $\text{result}$
- Execution log $\text{log}$
- Shallow roadmap $\text{roadmap}$

**Output:**
- Reviewer decision $\text{decision}$

---

**if** $\neg \text{SanityCheckResult}(\text{result})$ **then**

$\quad$ **return** $\text{Decision}(\text{NEEDS\_REVISION}, \text{"Schema validation failed"})$

**end if**

$\text{review} \leftarrow \text{SemanticReview}(\text{task}, \text{result}, \text{log})$

**if** $\text{review}.\text{approved}$ **then**

$\quad \text{updates} \leftarrow \text{ConsolidateContext}(\text{task}, \text{result}, \text{roadmap})$

$\quad$ **return** $\text{Decision}(\text{APPROVED}, \text{updates}, \text{review}.\text{evidence})$

**else if** $\text{review}.\text{needs\_revision}$ **then**

$\quad$ **return** $\text{Decision}(\text{NEEDS\_REVISION}, \text{review}.\text{rationale})$

**else if** $\text{review}.\text{replan\_needed}$ **then**

$\quad$ **return** $\text{Decision}(\text{REPLAN}, \text{review}.\text{rationale})$

**else**

$\quad$ **return** $\text{Decision}(\text{REJECTED}, \text{review}.\text{rationale})$

**end if**

---

**Algorithm 7:** Pseudocode of task analyzer

**Function:** $\text{TaskAnalyzer}(\text{input\_data}, \text{rationale})$

**Input:**
- Input data $\text{input\_data}$ (digest, task context, or rationale)
- Optional rationale $\text{rationale}$

**Output:**
- List of tasks $T$

---

$T \leftarrow \text{AnalyzeAndDecompose}(\text{input\_data}, \text{rationale})$

$\text{ValidateSequentialStructure}(T)$

**return** $T$

---

**Algorithm 8:** Pseudocode of context propagation

**Function:** $\text{PropagateContext}(T, \text{approved\_task}, \text{review})$

**Input:**
- Task tree $T$
- Approved task $\text{approved\_task}$
- Review decision $\text{review}$

**Output:**
- Updated task tree $T$

---

$\text{future} \leftarrow \text{GetFutureTasks}(T, \text{approved\_task})$

**for each** $\text{update} \in \text{review}.\text{context\_updates}$ **do**

$\quad \text{target} \leftarrow \text{FindTargetTask}(T, \text{update}.\text{target\_task\_id})$

$\quad$ **if** $\text{target} \neq \text{null}$ **then**

$\quad\quad \text{UpdateTaskContext}(\text{target}, \text{update})$

$\quad$ **end if**

**end for**

---

**Algorithm 9:** Pseudocode of result aggregation

**Function:** $\text{ResultAggregationNode}(T)$

**Input:**
- Completed task tree $T$

**Output:**
- Aggregated result $\text{aggregate}$

---

$\text{approved} \leftarrow \text{CollectApprovedResults}(T)$

$\text{aggregate} \leftarrow \text{StructureForResponse}(\text{approved})$

**return** $\text{aggregate}$

---

## Key Design Principles

1. **Context Decomposition:** Work decomposition is a means to context decomposition. Each internal agent receives only the context needed for its responsibility.

2. **Sequential Execution:** The Worker is a sequential roadmap executor, not a parallel scheduler. Parallelization belongs inside individual task execution.

3. **Stateful Recovery:** The Result Reviewer uses structured recovery budgets instead of simple retry counts.

4. **Targeted Propagation:** Context updates are targeted to specific future tasks, not dumped into all future contexts.

5. **Hybrid Review:** Deterministic checks validate schema and structure before LLM-based semantic review evaluates correctness and sufficiency.
