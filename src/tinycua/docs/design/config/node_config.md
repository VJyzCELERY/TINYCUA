# Node Configuration

> **Package:** `tinycua.config.node_config`
> **Status:** Target architecture

## Role

Each concrete TinyCUA node has its own config dataclass. Node config controls node
behavior, not SDK model/provider configuration.

## NodeMessageStrategy

`NodeMessageStrategy` controls how a node selects reusable session context and formats
non-system continuation messages. It does not change the system prompt rendering contract.

```text
NodeMessageStrategy
  · include_chat_history: bool = false
  · include_session_context: bool = true
  · max_context_messages: int | None
  · dedupe_by_origin_record_id: bool = true
  · continuation_role: "assistant"
```

Nodes may specialize this strategy, but internal node handoffs and continuations remain
assistant-role messages unless a provider-specific tool role is required.

## Base Config

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
hardcoded static instruction and optional dynamic system context through the prompt
builder defined in [`../loops/node.md`](../loops/node.md). Prompt fragments are kept
separate internally and rendered into **one final system-role message** for LLM calls.

```text
Prompt builder
  → add_static(hardcoded_instruction)
  → add_configurable_append(custom_instruction_append)
  → add_dynamic_context(dynamic_system_context)
  .build() → {"role": "system", "content": ordered_merged_content}
```

The dynamic system context is built by the node, not arbitrary user text. Examples:

- current active task
- node-local state summary
- output schema reminders
- active tool policy

TinyCUA keeps prompt parts structured internally and always renders one system message
at the LLM boundary for provider portability.

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

## NodeRetryPolicy

```text
NodeRetryPolicy
  · max_attempts
  · required_tool_calls
  · required_output_schema
  · validation_fn
  · retry_continuation_builder
  · on_retry_exhausted
```

Retry prompts are assistant-role continuations.

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
