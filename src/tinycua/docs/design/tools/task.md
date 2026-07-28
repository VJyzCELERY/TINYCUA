# Task Tools

> **Status:** Target architecture

Task tools are exposed according to node tool scope. Structural task tool calls directly
mutate the root `session.task` through TinyCUALoop task helpers; nodes do not return
opaque mutation instructions for TinyCUALoop to apply later.

| Node | Task Tool Scope |
|------|-----------------|
| TinyCUAQueryAnalystNode | read-only task inspection only |
| TinyCUAWorkerNode | worker decision tools only |
| TinyCUATaskCreateNode | deterministic root task creation only (TaskInit/TaskCreate) |
| TinyCUATaskAnalyzerNode | structural task tools; TaskInit/TaskCreate only when recreation is requested |
| TinyCUATaskAssessorNode | read-only inspection and assessment-decision tools |
| TinyCUATaskExecutorNode | active task execution and task result update tools |
| TinyCUAResultReviewerNode | review decision and task result/context update tools |

## Path-Specific Tool Semantics

Worker routes determine which tools `TaskAnalyzerNode` may use:

- **task_creation**: `TaskCreateNode` creates the root task deterministically; `TaskAnalyzerNode` runs after root creation and does NOT need TaskInit/TaskCreate authority.
- **task_recreation**: `TaskAnalyzerNode` may use TaskInit/TaskCreate tools because replacement is explicitly requested (LLM-assisted).
- **task_reanalysis**: `TaskAnalyzerNode` must NOT use TaskInit/TaskCreate tools; it refines an existing task tree.

Task replacement/sharing follows session propagation and task sharing rules in
[`../models/session.md`](../models/session.md).

`task_decompose` refines a task only when distinct scoped contributions materially improve
execution or review. Children collectively advance the retained parent, may themselves be
decomposed later, and need enough context and observable evidence for their current
granularity. The tool keeps adequate work together and never requires atomic steps, a
fixed number of children, depth, or a sequential implementation recipe.

## Related

- [`../loops/worker_concept.md`](../loops/worker_concept.md)
- [`../config/node_config.md`](../config/node_config.md)
