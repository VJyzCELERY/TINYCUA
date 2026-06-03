# Tool Constants and Node Tool Scope

> **Status:** Target architecture

TinyCUA nodes expose tools through `NodeToolPolicy`.

```text
NodeToolPolicy
  · node_tools
  · include_agent_tools: none | selected | all
  · allowed_agent_tool_names
  · denied_agent_tool_names
```

The outer SDK `Agent(tools=[...])` remains the caller-provided tool pool. TinyCUA chooses
which nodes can see those tools.

| Node | Tool Scope |
|------|------------|
| TinyCUAQueryAnalystNode | classification + read-only task/context tools |
| TinyCUAInformationDigesterNode | enhanced retrieval + digest tools |
| TinyCUAWorkerNode | decision/classification tools only |
| TinyCUATaskAnalyzerNode | task structure tools; TaskInit/TaskCreate only when allowed |
| TinyCUATaskExecutorNode | task execution tools + selected outer Agent tools |
| TinyCUAResultReviewerNode | review/decision tools |
| TinyCUAResponseNode | selected outer Agent tools + information-digestion request capability |

## Related

- [`../config/node_config.md`](../config/node_config.md)
- [`../tools/digester.md`](../tools/digester.md)
- [`../tools/task.md`](../tools/task.md)
