# TinyCUAWorker AgentGraph

> **File:** `docs/design/orchestration/worker.md`
> **Package:** `tinycua.orchestration.worker`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`TinyCUAWorker` is an AgentGraph subgraph responsible for task creation,
decomposition, execution, review, retry, and replan. It can be used as a node inside
the top-level `TinyCUA` graph.

If it has a parent session, the worker explicitly inherits the parent's task reference
and participates in parent task sharing (`share_parent_task=True` by default). Task
replacement propagates according to the `Session.share_parent_task` algorithm.

---

## Worker Graph Shape

```text
TinyCUAWorker AgentGraph
  ├── InputGate(QueryAnalystNode)     # classification configured for worker routing
  ├── TaskAnalyzerNode                # with or without TaskInit depending on input-gate classification
  ├── TaskDecompositionOuterLoop      # TaskAssessor → TaskAnalyzer, repeated by WorkerEffort
  ├── TaskExecutorNode
  └── ResultReviewerNode              # accept | retry | replan | open-question
```

`TaskCreation` does not have to be a separate AgentNode. The simpler source of truth is
the Worker graph itself orchestrating `TaskAnalyzer` and `TaskAssessor`. If future
implementation benefits from encapsulation, the `TaskAnalyzer → TaskAssessor` loop may
be wrapped as a composite node without changing external Worker behavior.

---

## Input Gate

The worker has its own QueryAnalyst input gate using worker-specific classification
labels:

```text
TINYCUA_WORKER_INPUT_GATE_CLASSIFICATION = [
    "task_recreation",      # run TaskAnalyzer with TaskInit
    "task_reanalysis",      # run TaskAnalyzer without TaskInit against existing task
    "proceed_execution",    # skip analysis/decomposition; go to executor/reviewer loop
]
```

The labels are configured through `QueryAnalystConfig.classification_labels`, not by
hardcoding a separate QueryAnalyst implementation.

---

## Main Routes

```text
InputGate(QueryAnalyst)
  ├── task_recreation
  │     → TaskAnalyzer(with TaskInit)
  │     → TaskDecompositionOuterLoop(if effort applies)
  │     → TaskExecutor
  │     → ResultReviewer
  │     → ReviewRoute
  │
  ├── task_reanalysis
  │     → TaskAnalyzer(without TaskInit)
  │     → TaskDecompositionOuterLoop(if effort applies)
  │     → TaskExecutor
  │     → ResultReviewer
  │     → ReviewRoute
  │
  └── proceed_execution
        → TaskExecutor
        → ResultReviewer
        → ReviewRoute
```

The worker may receive any of these input strings:

| Input | Handling |
|-------|----------|
| Plain `str` query | Worker input gate classifies it |
| `QueryAnalystState` YAML front-matter | Use worker-specific classification: `task_recreation`, `task_reanalysis`, or `proceed_execution` |
| `InformationDigesterState` YAML front-matter | Usually triggers task recreation or reanalysis |
| `ResultReviewerState` YAML front-matter | Usually routes to retry/replan handling |

All inputs still satisfy the universal `run(query: str)` contract. Structured state is
parsed with `AgentState.from_string(query)`.

---

## Task Decomposition OuterLoop

The decomposition loop happens outside the SDK Agent loop. It is graph-level control
flow, not an internal `Agent.run()` loop.

```text
TaskDecompositionOuterLoop(effort):
  · if effort is None: skip
  · else repeat N passes determined by WorkerEffort:
      1. TaskAssessor assesses current task tree
      2. if verdict == "stop": break
      3. TaskAnalyzer updates tree from assessor analysis
```

TaskAnalyzer can receive `TaskInit` only on the initial `task_recreation` route. Normal
decomposition passes do **not** include `TaskInit`.

---

## Task Analyzer Rules

- Avoid editing already completed tasks.
- If completed tasks obstruct planning, prune them from the working task tree rather
  than rewriting their content.
- `TaskInit` is only available when worker input classification is `task_recreation`.
- In all other cases, TaskAnalyzer uses structural task tools (`SetSubTask`,
  `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, `UpdateTaskResult`) but
  not wholesale task replacement.

---

## Task Assessor Rules

- Avoid selecting completed tasks for update.
- Assessment targets incomplete or blocked branches.
- If no incomplete branch requires analysis, return `stop`.

---

## Execution + Review Loop

`TaskExecutor` and `ResultReviewer` are orchestrated by the Worker graph:

```text
TaskExecutor
  → writes TaskExecutorState + active Task.task_result
  → ResultReviewer
      ├── accept → apply context updates to unfinished tasks; continue to next active task or finish
      ├── retry  → mark active task not_started + append retry context; route back to TaskExecutor
      ├── replan → TaskAssessor → TaskAnalyzer; active task may change; then route to TaskExecutor
      └── no decision/open question → keep ResultReviewer active; next user query passthrough returns here
```

`ResultReviewer` has no `escalate_user` decision. Human-in-the-loop happens by leaving
the reviewer active with an open question.

---

## Task Propagation

When the worker creates a new task tree, it propagates the replacement through the
current task-sharing group:

```text
worker.session.task = new_task
worker.session.propagate_task_replacement(new_task)
```

Propagation walks upward until a `share_parent_task=False` boundary, then downward to
all descendants that remain within the same sharing group. See
[Session task sharing](../state/session.md#task-sharing-and-propagation).

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Worker is AgentGraph | Subgraph node inside TinyCUA | Keeps task planning/execution routing separate from top-level chat routing |
| Own input gate | QueryAnalyst with worker-specific labels | Same ClassificationTool mechanism, different decision space |
| TaskCreation not mandatory node | Worker graph owns TaskAnalyzer ↔ TaskAssessor loop | Simpler source of truth; can wrap later if needed |
| OuterLoop outside SDK Agent | Graph-level loop over AgentNodes | Deterministic effort control; no hidden LLM loop |
| TaskInit only on recreation | Conditional tool injection | Prevents destructive task resets during normal analysis |
| Execution/review loop in Worker | Worker routes TaskExecutor ↔ ResultReviewer | Result review decisions are graph-routing decisions |
| No escalate_user | Open question keeps reviewer active | HITL through passthrough, not special mode |

---

## See also

Prev : [`RouterNode`](router_node.md) | Next : [`AgentNode Call Tools`](../tools/agent_calls.md)

## Related

- [Top-level TinyCUA routes worker mode here](tinycua.md)
- [Task sharing and propagation](../state/session.md#task-sharing-and-propagation)
- [TaskAnalyzer rules](../agent_sessions/task_analyzer.md)
- [ResultReviewer routing](../agent_sessions/result_reviewer.md)
- [WorkerConfig effort](../state/worker_result.md)
