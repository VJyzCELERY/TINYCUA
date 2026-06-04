# Task Tools

> **Status:** Target architecture

Task tools are exposed according to node tool scope.

| Node | Task Tool Scope |
|------|-----------------|
| TinyCUAQueryAnalystNode | read-only task inspection only |
| TinyCUAWorkerNode | worker decision tools only |
| TinyCUATaskCreateNode | deterministic root task creation only (TaskInit/TaskCreate) |
| TinyCUATaskAnalyzerNode | structural task tools; TaskInit/TaskCreate only when recreation is requested |
| TinyCUATaskAssessorNode | task assessment/read/update tools as needed |
| TinyCUATaskExecutorNode | active task execution and task result update tools |
| TinyCUAResultReviewerNode | review decision and task result/context update tools |

## Path-Specific Tool Semantics

Worker routes determine which tools `TaskAnalyzerNode` may use:

- **task_creation**: `TaskCreateNode` creates the root task deterministically; `TaskAnalyzerNode` runs after root creation and does NOT need TaskInit/TaskCreate authority.
- **task_recreation**: `TaskAnalyzerNode` may use TaskInit/TaskCreate tools because replacement is explicitly requested (LLM-assisted).
- **task_reanalysis**: `TaskAnalyzerNode` must NOT use TaskInit/TaskCreate tools; it refines an existing task tree.

Task replacement/sharing follows session propagation and task sharing rules in
[`../models/session.md`](../models/session.md).

## Related

- [`../loops/worker_concept.md`](../loops/worker_concept.md)
- [`../config/node_config.md`](../config/node_config.md)
