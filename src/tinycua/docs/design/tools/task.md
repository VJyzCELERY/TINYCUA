# Task Tools

> **Status:** Target architecture

Task tools are exposed according to node tool scope.

| Node | Task Tool Scope |
|------|-----------------|
| TinyCUAQueryAnalystNode | read-only task inspection only |
| TinyCUAWorkerNode | worker decision tools only |
| TinyCUATaskAnalyzerNode | structural task tools; TaskInit/TaskCreate only when task is missing or recreation is requested |
| TinyCUATaskAssessorNode | task assessment/read/update tools as needed |
| TinyCUATaskExecutorNode | active task execution and task result update tools |
| TinyCUAResultReviewerNode | review decision and task result/context update tools |

Task replacement/sharing follows session propagation and task sharing rules in
[`../models/session.md`](../models/session.md).

## Related

- [`../loops/worker_concept.md`](../loops/worker_concept.md)
- [`../config/node_config.md`](../config/node_config.md)
