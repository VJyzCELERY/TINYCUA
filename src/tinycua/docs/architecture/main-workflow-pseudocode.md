# TINYCUA Main Workflow Pseudocode

> **Category:** Architecture Explanation

> **File:** `architecture/main-workflow-pseudocode.md`
> **Last Updated:** 2026-07-21
> **Status:** Reviewer-ready explanation
> **See also:** [overview.md](overview.md), [worker-orchestration.md](worker-orchestration.md), [information-digestion.md](information-digestion.md), [task-creation.md](task-creation.md), [task-analysis.md](task-analysis.md), [task-assessor.md](task-assessor.md), [task-execution.md](task-execution.md), [result-reviewer.md](result-reviewer.md), [state-objects.md](state-objects.md)

This document provides manuscript-ready pseudocode for the main TINYCUA workflow.
It is intended to answer reviewer requests for an algorithmic explanation of the
workflow shown in the main-flow diagram.

---

## Reviewer Summary

TINYCUA routes each user query through a lightweight Query Analyst. Simple requests
can pass directly to response synthesis. Work-intensive requests are first condensed
by the Information Digester, then processed by a Worker that creates a task tree,
executes only leaf tasks, reviews every task result, propagates accepted context to
future tasks, and aggregates accepted results before producing the final response.

---

## Algorithm 1: TINYCUA Main Workflow

```latex
\begin{algorithm}[t]
\caption{TINYCUA main workflow}
\label{alg:tinycua-main-workflow}
\begin{algorithmic}[1]
\Require User query $q$, session context $C$, worker effort $e$
\Ensure Final user response $r$

\State $(q', route) \gets \textsc{QueryAnalyst}(q, C)$
\If{$route = \textsc{Passthrough}$}
    \State $r \gets \textsc{ResponseNode}(q', C)$
    \State \Return $r$
\EndIf

\State $d \gets \textsc{InformationDigester}(q', C)$
\State $workerRoute \gets \textsc{WorkerRoute}(d)$

\If{$workerRoute = \textsc{Passthrough}$}
    \State $r \gets \textsc{ResponseNode}(d, C)$
    \State \Return $r$
\ElsIf{$workerRoute = \textsc{TaskCreation}$}
    \State $T \gets \textsc{CreateTaskTree}(d, e)$
\ElsIf{$workerRoute \in \{\textsc{TaskRecreation}, \textsc{TaskReanalysis}\}$}
    \State $T \gets \textsc{TaskAnalyzer}(d, T)$
\EndIf

\While{$\exists$ unfinished leaf task in $T$}
    \State $t \gets \textsc{SelectNextUnfinishedLeaf}(T)$
    \State $y \gets \textsc{TaskExecutor}(t, \textsc{ShallowRoadmap}(T))$
    \State $v \gets \textsc{ResultReviewer}(t, y, \textsc{ExecutionLog}(t), \textsc{ShallowRoadmap}(T))$

    \If{$v.status = \textsc{Approved}$}
        \State $\textsc{PropagateContext}(T, t, v)$
        \State $\textsc{MarkAccepted}(T, t, y, v)$
    \ElsIf{$v.status \in \{\textsc{NeedsRevision}, \textsc{Rejected}\}$}
        \State $\textsc{RecordFailureContext}(t, v)$
        \State \textbf{continue}
    \ElsIf{$v.status = \textsc{Replan}$}
        \State $S \gets \textsc{TaskAnalyzer}(t.context, v.rationale)$
        \State $\textsc{ReplaceLeafWithSubtasks}(T, t, S)$
        \State \textbf{continue}
    \EndIf
\EndWhile

\State $a \gets \textsc{ResultAggregationNode}(T)$
\State $r \gets \textsc{ResponseNode}(a)$
\State \Return $r$
\end{algorithmic}
\end{algorithm}
```

---

## Algorithm 2: Task Tree Creation

```latex
\begin{algorithm}[t]
\caption{TINYCUA task-tree creation}
\label{alg:tinycua-task-tree-creation}
\begin{algorithmic}[1]
\Require Digested information $d$, worker effort $e$
\Ensure Sequential task tree $T$

\State $T \gets \textsc{TaskAnalyzer}(d)$
\State $p_{max} \gets \textsc{AnalysisEffortNode}(e)$
\For{$p = 1$ to $p_{max}$}
    \State $S \gets \textsc{TaskAssessor}(T)$
    \If{$S = \emptyset$}
        \State \textbf{break}
    \EndIf
    \ForAll{$t \in S$}
        \State $children \gets \textsc{TaskAnalyzer}(t.context)$
        \State $\textsc{AttachChildren}(T, t, children)$
    \EndFor
\EndFor
\State \Return $T$
\end{algorithmic}
\end{algorithm}
```

---

## Notes For Manuscript Text

- The Query Analyst is a routing node. It decides whether a request should pass
  through to response synthesis or enter Worker mode.
- The Information Digester is a context-narrowing node. It gathers and condenses
  relevant context before Worker planning begins.
- The Worker is a sequential controller, not a parallel scheduler. It executes one
  unfinished leaf task at a time.
- Task Creation builds the initial task tree by alternating Task Analyzer and Task
  Assessor passes according to the configured effort level.
- The Task Executor performs the concrete work for one leaf task using task-scoped
  context and shallow roadmap awareness.
- The Result Reviewer gates progress. Accepted results update future task context;
  rejected or revision-needed results return to execution; replan decisions invoke
  the Task Analyzer to replace the current leaf with subtasks.
- Result Aggregation collects accepted task results into response-ready context, and
  ResponseNode produces the final user-facing answer.

---

## Compact Plain-Text Version

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
