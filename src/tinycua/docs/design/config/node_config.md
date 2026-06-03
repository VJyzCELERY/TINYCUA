# Node Configuration

> **Package:** `tinycua.config.node_config`
> **Status:** Target architecture

## Role

Each concrete TinyCUA node has its own config dataclass. Node config controls node
behavior, not SDK model/provider configuration.

```text
NodeConfigBase
  · custom_instruction_append: str | None
  · custom_continuation_append: str | None
  · custom_retry_append: str | None
  · propagation: PropagationRule
  · tool_policy: NodeToolPolicy
  · stream_policy: NodeStreamPolicy
  · retry_policy: NodeRetryPolicy
  · message_strategy: NodeMessageStrategy
  · metadata: dict
```

Customization is append-only:

```text
hardcoded_instruction_constant + custom_instruction_append
hardcoded_continuation_constant + custom_continuation_append
hardcoded_retry_constant + custom_retry_append
```

## System Prompt Rendering

Node config contributes only append-only instruction content. The node combines it with
hardcoded static instruction and optional dynamic system context in a structured
`SystemPromptBundle` before rendering messages.

```text
SystemPromptBundle.to_messages():
  → {"role": "system", "content": static_instruction}
  → {"role": "system", "content": custom_instruction_append}
  → {"role": "system", "content": dynamic_system_context}
```

The dynamic system context is built by the node, not arbitrary user text. Examples:

- current active task
- node-local state summary
- output schema reminders
- active tool policy

Current SDK canonical messages allow multiple system messages to pass through. If a
future provider requires a single system message, TinyCUA should merge prompt parts at
render time while keeping them separate internally.

## NodeToolPolicy

```text
NodeToolPolicy
  · node_tools
  · include_agent_tools: none | selected | all
  · allowed_agent_tool_names
  · denied_agent_tool_names
```

## NodeStreamPolicy

```text
NodeStreamPolicy
  · visible_to_user: bool = true
  · emit_internal_events: bool = configurable
  · include_node_metadata: bool = true
  · final_response_only: bool = false
```

When `stream=True`, LLM/tool events from every node are streamable to the caller.

## Per-Node Configs

- `TinyCUAQueryAnalystNodeConfig`
- `TinyCUAInformationDigesterNodeConfig`
- `TinyCUAWorkerNodeConfig`
- `TinyCUATaskAnalyzerNodeConfig`
- `TinyCUATaskAssessorNodeConfig`
- `TinyCUATaskExecutorNodeConfig`
- `TinyCUAResultReviewerNodeConfig`
- `TinyCUAResponseNodeConfig`

## Related

- [`../loops/node.md`](../loops/node.md)
- [`session_config.md`](session_config.md)
