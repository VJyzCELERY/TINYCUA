# Task Executor AgentNode Spec Card

Source of truth: [`agent_sessions/task_executor.md`](../agent_sessions/task_executor.md).

## Summary

- Executes current active leaf task.
- Uses `SHARED_AGENT_BASE_TOOLS` + active-task tools.
- Writes active `Task.task_result` via `UpdateActiveTaskResult`.
- Emits `TaskExecutorState` to `session.agent_state`.
- Terminal statuses: `completed`, `failed`, `blocked`.

## Related

- [TaskExecutorState](../state/information.md#taskexecutorstate)
- [Task tools](../tools/task.md)
- [TinyCUAWorker execution loop](../orchestration/worker.md#execution--review-loop)
