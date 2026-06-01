# Task Analyzer AgentNode Spec Card

Source of truth: [`agent_node/task_analyzer.md`](../agent_node/task_analyzer.md).

## Summary

- Worker-orchestrated AgentNode.
- Parses AgentState YAML front-matter.
- `TaskInit` is injected only for worker `task_reanalysis` when no task tree exists.
- Avoids editing completed tasks; may prune completed tasks when needed.
- Mutates `session.task` via task tools.
- Emits `TaskAnalyzerState` to `session.agent_state`.

## Related

- [TinyCUAWorker](../orchestration/worker.md)
- [TaskAnalyzerState](../state/information.md#taskanalyzerstate)
- [Task tools](../tools/task.md)
