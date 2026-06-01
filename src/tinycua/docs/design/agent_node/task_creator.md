# Task Creator

> **File:** `docs/design/agent_node/task_creator.md`
> **Package:** `tinycua.agent_nodes.task_creator`
> **Last Updated:** 2026-06-01
> **Status:** Deprecated/Optional Composite

---

## Role

`TaskCreator` is no longer the primary source of truth for task creation flow. The
canonical design is `TinyCUAWorker` directly orchestrating:

```text
TaskAnalyzer → TaskDecompositionOuterLoop(TaskAssessor → TaskAnalyzer)
```

`TaskCreator` may remain as an optional composite wrapper if implementation benefits
from encapsulating that flow, but it must preserve the Worker semantics documented in
[orchestration/worker.md](../orchestration/worker.md).

---

## If Implemented as Composite Node

```text
TaskCreator(BaseAgentNode)  ← optional composite over TaskAnalyzer + TaskAssessor

run(query: str) -> AsyncIterator[dict]
  · parse input AgentState YAML front-matter with AgentState.from_string(query)
  · if Worker classification == "task_recreation": terminate/restart at Worker level, not here
  · if Worker classification == "task_reanalysis" and no task exists: call TaskAnalyzer with TaskInit
  · if effort applies: run TaskAssessor → TaskAnalyzer outer loop
  · propagate task replacement via Session.share_parent_task rules
  · write TaskAnalyzerState or a future TaskCreatorState to session.agent_state
```

It must not hide or contradict Worker-level routing.

---

## TaskInit Rule

`TaskCreator` must inject `TaskInit` into TaskAnalyzer only when Worker input-gate
classification is `task_reanalysis` and the Worker has no task tree yet. It must not
handle `task_recreation` by creating a replacement tree in-place; that route belongs to
the Worker restart hand-off.

---

## Task Propagation

When a new task tree is created, the replacement is propagated through the current
task-sharing group according to `Session.share_parent_task`.

See [Session task sharing](../state/session.md#task-sharing-and-propagation).

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Worker is source of truth | Task creation flow documented in TinyCUAWorker | Avoid duplicate/contradictory orchestration specs |
| TaskCreator optional | Composite wrapper only | Allows simpler implementation if useful |
| No independent semantics | Must mirror Worker rules | Prevents drift |
| TaskInit conditional | Only when reanalysis starts without a task tree | Prevents destructive resets |

---

## See also

Prev : [`TaskAssessor`](task_assessor.md) | Next : [`TaskExecutor`](task_executor.md)

## Related

- [TinyCUAWorker task creation source of truth](../orchestration/worker.md)
- [TaskAnalyzer](task_analyzer.md)
- [TaskAssessor](task_assessor.md)
- [Session task sharing](../state/session.md#task-sharing-and-propagation)
