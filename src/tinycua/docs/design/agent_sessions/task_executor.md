# Task Executor

> **File:** `docs/design/agent_sessions/task_executor.md`
> **Package:** `tinycua.agent_nodes.task_executor`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`TaskExecutor` executes the current active executable leaf task. It does not receive a
task object directly; it dynamically inspects `session.task` with task tools.

The active task's outcome is written through `UpdateActiveTaskResult`, and the loop
writes `TaskExecutorState` to `session.agent_state`.

---

## `run()` Method

```text
run(query: str) -> AsyncIterator[dict]
```

`query` is a plain execution instruction, a user steering message, or a YAML-front-
matter state string from Worker/ResultReviewer. The executor may parse structured
state with `AgentState.from_string(query)`, but task details are loaded by tools.

---

## Tools

```text
TASK_EXECUTOR_BASE_TOOLS = [
    *SHARED_AGENT_BASE_TOOLS,
    ReadActiveTask,
    ListTask,
    UpdateActiveTaskResult,
]
```

TaskExecutor shares the same general execution surface as PrimaryAgent and adds only
the active-task tools it needs. It cannot update arbitrary task IDs.

---

## ReAct Phase Structure

TaskExecutor follows the standard **Analyze → Plan → ReAct** phase structure:

1. **ANALYZE**: Read active task, inspect task tree, read TodoList.
2. **PLAN**: Use TodoList to record concrete execution steps.
3. **ReAct**: Execute steps, observe results, update TodoList and active task result.

TodoList is short-term working memory; Task Tree is the formal roadmap.

---

## Termination

TaskExecutor termination is tied to the active task's `TaskResult.status`:

| Status | Lifecycle |
|--------|-----------|
| `completed` | Terminal |
| `failed` | Terminal |
| `blocked` | Terminal |
| `inprogress` | Non-terminal — executor remains active |
| `not_started` | Non-terminal — executor remains active |

If the executor does not write a terminal result, it remains active and can receive
passthrough messages.

---

## Output: TaskExecutorState

```text
TaskExecutorState(
  type="task_executor",
  status="terminated" | "running" | "blocked",
  failure=N,
  task_id="T-0.1",
  task_result=TaskResult(...),
  execution_attempts=N,
  tool_results=[...],
)
```

The authoritative task outcome is still stored on the active `Task.task_result`.
`TaskExecutorState` is the cross-node state passed to ResultReviewer.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Task loaded by tools | No task object in `run()` | Executor always sees latest shared task state |
| Shared base tools | `SHARED_AGENT_BASE_TOOLS` | Execution tasks need general tool surface |
| Active-result scope | `UpdateActiveTaskResult` only | Prevents writing result to wrong task |
| ReAct phases | Instruction-level Analyze→Plan→ReAct | Behavioral guidance without code dispatch |
| AgentState output | `TaskExecutorState` | Serializable input for ResultReviewer |

---

## See also

Prev : [`TaskAssessor`](task_assessor.md) | Next : [`ResultReviewer`](result_reviewer.md)

## Related

- [TaskExecutorState](../state/information.md#taskexecutorstate)
- [Task tools](../tools/task.md)
- [ReAct loop](../loops/react_agent.md)
- [TinyCUAWorker execution loop](../orchestration/worker.md#execution--review-loop)
