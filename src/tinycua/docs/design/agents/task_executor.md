# Task Executor AgentNode Spec Card

Source of truth: [`agent_node/task_executor.md`](../agent_node/task_executor.md). This is a navigation summary — for implementation details, see the source-of-truth doc.

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
