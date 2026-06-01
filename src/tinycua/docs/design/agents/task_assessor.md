# Task Assessor AgentNode Spec Card

Source of truth: [`agent_sessions/task_assessor.md`](../agent_sessions/task_assessor.md).

## Summary

- Worker OuterLoop AgentNode.
- Read-only task inspection.
- Classification labels: `analyze`, `stop`.
- Avoids selecting completed tasks for updates.
- Emits `TaskAssessorState` to `session.agent_state`.

## Related

- [TinyCUAWorker OuterLoop](../orchestration/worker.md#task-decomposition-outerloop)
- [TaskAssessorState](../state/information.md#taskassessorstate)
