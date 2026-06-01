# TaskExecutorLoop

> **File:** `docs/design/loops/task_executor_loop.md`
> **Last Updated:** 2026-06-01

---

## Role

Observes `UpdateActiveTaskResult`, mirrors the active task result into
`TaskExecutorState`, and decides whether TaskExecutor remains active.

```text
session.agent_state = TaskExecutorState(
  type="task_executor",
  status="terminated" | "running" | "blocked",
  task_id=active_task.task_id,
  task_result=active_task.task_result,
  execution_attempts=N,
)
```

Terminal task statuses: `completed`, `failed`, `blocked`.

---

## Related

- [TaskExecutor AgentNode](../agent_sessions/task_executor.md)
- [TaskExecutorState](../state/information.md#taskexecutorstate)
