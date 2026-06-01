# Task Assessor AgentNode Spec Card

Source of truth: [`agent_node/task_assessor.md`](../agent_node/task_assessor.md). This is a navigation summary — for implementation details, see the source-of-truth doc.

## Summary

- Worker OuterLoop AgentNode.
- Read-only task inspection.
- Classification labels: `analyze`, `stop`.
- Avoids selecting completed tasks for updates.
- Emits `TaskAssessorState` to `session.agent_state`.

## Related

- [TinyCUAWorker OuterLoop](../orchestration/worker.md#task-decomposition-outerloop)
- [TaskAssessorState](../state/information.md#taskassessorstate)
