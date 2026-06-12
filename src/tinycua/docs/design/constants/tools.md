# Tool Constants and Node Tool Scope

> **Status:** Target architecture

TinyCUA nodes expose tools through the tool policy defined in
[`../config/node_config.md`](../config/node_config.md).

The outer SDK `Agent(tools=[...])` remains the caller-provided tool pool. TinyCUA chooses
which nodes can see those tools.

| Node | Tool Scope |
|------|------------|
| TinyCUAQueryAnalystNode | classification + read-only task/context tools |
| TinyCUAInformationDigesterNode | enhanced retrieval + digest tools |
| TinyCUAWorkerNode | worker decision tools only |
| TinyCUATaskCreateNode | deterministic root task creation tools (TaskInit/TaskCreate) |
| TinyCUATaskAnalyzerNode | task structure tools; TaskInit/TaskCreate only when recreation is requested |
| TinyCUATaskAssessorNode | task assessment/read/update tools as needed |
| TinyCUATaskExecutorNode | task execution tools + selected outer Agent tools + `enhanced_context_retrieval` + exploration/web/context search tools when enabled |
| TinyCUAResultReviewerNode | review/decision tools |
| TinyCUAResponseNode | same base toolset as TinyCUATaskExecutorNode + final response/synthesis behavior + optional information-digestion request capability only when enabled |

## TaskExecutor Direct Context Retrieval

`TaskExecutor` does not spawn `InformationDigesterNode`. If `TaskExecutor` needs more
context, it calls `enhanced_context_retrieval` directly.

## WorkerNode Information Digestion

`QueryAnalyst` spawns `InformationDigesterNode` before routing to `WorkerNode`.
The digester gathers and digests context, then propagates the output to the Worker's
session. Worker receives DigestedInformation as input and uses it for routing decisions.

## ResponseNode Same Base Toolset

`ResponseNode` has the same base toolset as `TaskExecutor`, plus final response/synthesis
behavior and optional information-digestion request capability only when enabled.

## Enhanced Context Retrieval

`enhanced_context_retrieval` is a tool available to `InformationDigesterNode`,
`TaskExecutor`, and `ResponseNode`:

- Receives the current session or selected session_context.
- Lazily creates a scoped context cache file when called.
- The cache contains only selected context for that session/tool call.
- Retrieval runs as a ReAct-style search over the cache.
- Search/read tools are limited to grep/search within the cache and paginated cache reads.
- `InformationDigesterNode` may call the tool, but the tool owns cache creation.

## Related

- [`../config/node_config.md`](../config/node_config.md)
- [`../tools/digester.md`](../tools/digester.md)
- [`../tools/task.md`](../tools/task.md)
