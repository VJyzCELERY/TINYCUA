# TINYCUA Main Workflow Pseudocode

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

**Step 1:** *Query Analyst — High-level context scan and routing*

$`q_{\text{enhanced}}, \text{route} \leftarrow \text{QueryAnalyst}(q, C)`$

**if** $`\text{route} = \text{PASSTHROUGH}`$ **then**

$\quad$ **return** $`\text{ResponseNode}(q_{\text{enhanced}}, C)`$

**end if**

---

**Step 2:** *Information Digester — Context condensation*

$`d \leftarrow \text{InformationDigester}(q_{\text{enhanced}}, C)`$

---

**Step 3:** *Task Tree Creation*

$`T \leftarrow \text{CreateTaskTree}(d, \text{effort})`$

---

**Step 4:** *Sequential Task Execution Loop*

**while** $`\exists`$ unfinished leaf task $t$ in $T$ **do**

$\quad$ *Select and execute next task*

$\quad t \leftarrow \text{SelectNextUnfinishedLeaf}(T)$

$\quad y \leftarrow \text{TaskExecutor}(t, \text{ShallowRoadmap}(T))$

$\quad$ *Review result*

$\quad v \leftarrow \text{ResultReviewer}(t, y, \text{ExecutionLog}(t), \text{ShallowRoadmap}(T))$

$\quad$ *Handle decision*

**if** $`v.\text{status} = \text{APPROVED}`$ **then**

$\quad\quad \text{PropagateContext}(T, t, v)$

$\quad\quad \text{MarkAccepted}(T, t, y, v)$

**else if** $`v.\text{status} = \text{NEEDS\_REVISION}`$ **then**

$\quad\quad \text{RecordFailureContext}(t, v)$

**else if** $`v.\text{status} = \text{REPLAN}`$ **then**

$\quad\quad S \leftarrow \text{TaskAnalyzer}(t.\text{context}, v.\text{rationale})$

$\quad\quad \text{ReplaceLeafWithSubtasks}(T, t, S)$

**end if**

**end while**

---

**Step 5:** *Result Aggregation and Response*

$`a \leftarrow \text{ResultAggregationNode}(T)`$

**return** $`\text{ResponseNode}(a)`$

---

## Key Components

| Component | Role |
|-----------|------|
| Query Analyst | High-level scan, route to passthrough or worker |
| Information Digester | Condense relevant context from session |
| Task Tree Creation | Build nested task tree via iterative decomposition |
| Task Executor | Execute one leaf task (ReAct loop) |
| Result Reviewer | Accept, revise, or replan task results |
| Result Aggregation | Collect approved results for response |
| Response Node | Generate final user-facing answer |

---

## Key Design Principles

1. **Context Decomposition:** Work decomposition enables context decomposition — each agent receives only needed context.

2. **Sequential Execution:** Worker executes one task at a time; parallelization belongs inside task execution.

3. **Stateful Recovery:** Structured recovery budgets replace simple retry counts.

4. **Targeted Propagation:** Context updates target specific future tasks, not all future contexts.
