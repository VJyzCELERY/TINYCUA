# Task Creator Optional Composite Spec Card

Source of truth: [`agent_sessions/task_creator.md`](../agent_sessions/task_creator.md).

## Summary

- Deprecated/optional composite wrapper.
- Canonical task creation flow now lives in [`orchestration/worker.md`](../orchestration/worker.md).
- If implemented, it must mirror TinyCUAWorker's TaskAnalyzer → TaskAssessor outer loop.
- Must inject `TaskInit` only for `task_recreation`.

## Related

- [TinyCUAWorker](../orchestration/worker.md)
- [TaskAnalyzer](task_analyzer.md)
- [TaskAssessor](task_assessor.md)
