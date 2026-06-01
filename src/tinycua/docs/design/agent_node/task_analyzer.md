# Task Analyzer

> **File:** `docs/design/agent_node/task_analyzer.md`
> **Package:** `tinycua.agent_nodes.task_analyzer`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`TaskAnalyzer` creates, decomposes, and updates the shared `Session.task` tree. It is
orchestrated by `TinyCUAWorker`, not directly by the top-level TinyCUA graph.

It receives `run(query: str)` input that may contain AgentState YAML front-matter
(`QueryAnalystState`, `InformationDigesterState`, `ResultReviewerState`, or
`TaskAnalyzerState`). It parses with `AgentState.from_string(query)` and adapts tools
accordingly.

---

## TaskInit Access Rule

`TaskInit` is destructive because it replaces the entire task tree. It is excluded
from `TASK_ANALYZER_BASE_TOOLS` by default.

TinyCUAWorker injects `TaskInit` only when its input gate classification is:

```text
classification == "task_recreation"
```

Otherwise, TaskAnalyzer modifies the existing tree using structural tools only:
`SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, and
`UpdateTaskResult`.

---

## Completed Task Policy

TaskAnalyzer should avoid updating or editing already completed tasks.

Allowed behavior:

- Leave completed tasks untouched.
- Prune completed tasks from the active working tree if they obstruct reanalysis.
- Add new tasks around completed work.
- Update incomplete, blocked, failed, in-progress, or not-started tasks.

Disallowed behavior:

- Rewrite completed task descriptions/results.
- Select completed tasks as active targets for update.

---

## `run()` Method

```text
run(query: str) -> AsyncIterator[dict]
```

Flow:

```text
run(query)
  1. parsed_state = AgentState.from_string(query)
  2. determine if TaskInit is available from Worker classification/config
  3. build instruction: base + current task tree display + completed-task policy
  4. build SDK Agent with TASK_ANALYZER_BASE_TOOLS (+ TaskInit if allowed)
  5. agent.run(query=query, messages=self.session.session_context, stream=True)
  6. TaskAnalyzerLoop stores TaskAnalyzerState on session.agent_state
```

---

## Tools

```text
TASK_ANALYZER_BASE_TOOLS = [
    *READ_ONLY_TASK_TOOLS,
    SetSubTask,
    AddSubTask,
    DeleteSubTask,
    EditSubTask,
    SwapTask,
    UpdateTaskResult,
]

if worker_classification == "task_recreation":
    tools += [TaskInit]
```

TaskAnalyzer never receives `UpdateActiveTaskResult`; that tool is reserved for
TaskExecutor and narrowly scoped review retry handling.

---

## Output: TaskAnalyzerState

```text
TaskAnalyzerState(
  type="task_analyzer",
  status="terminated",
  failure=0,
  analysis_summary="## Task Analysis Summary\n...",
)
```

The task tree itself is updated through task tools on `session.task`. The state stores
a human-readable summary of what changed and why.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Worker-orchestrated | Called by TinyCUAWorker | Task planning belongs inside worker subgraph |
| Conditional TaskInit | Only for `task_recreation` | Prevents accidental destructive reset |
| Completed tasks protected | Avoid editing; prune if needed | Completed work should remain stable |
| Tool-based mutation | Task tools update `session.task` | Task tree is source of truth |
| AgentState output | `TaskAnalyzerState` | Serializable summary for downstream nodes |

---

## See also

Prev : [`InformationDigester`](information_digester.md) | Next : [`TaskAssessor`](task_assessor.md)

## Related

- [TinyCUAWorker routes TaskAnalyzer](../orchestration/worker.md)
- [Task tools](../tools/task.md)
- [TaskAnalyzerState](../state/information.md#taskanalyzerstate)
