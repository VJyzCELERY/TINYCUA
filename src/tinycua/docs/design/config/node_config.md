# Node Configuration

> **Package:** `tinycua.config.node_config`
> **Status:** Target architecture

## Role

Each concrete TinyCUA node has its own config dataclass. Node config controls node
behavior, not SDK model/provider configuration.

## NodeMessagePolicy

`NodeMessagePolicy` controls how a node selects reusable session context and formats
non-system continuation messages. It does not change the system prompt rendering contract.

```text
NodeMessagePolicy
  · include_chat_history: bool = false
  · include_session_context: bool = true
  · max_context_messages: int | None
  · dedupe_by_origin_record_id: bool = true
  · continuation_role: Literal["assistant"] = "assistant"
```

Internal node handoffs and continuations are assistant-role messages. Provider-required
tool roles are handled by provider/tool message translation, not by changing
`continuation_role`.

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
  · message_policy: NodeMessagePolicy
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
  · node_tools: list[Tool]
  · include_agent_tools: none | selected | all
  · allowed_agent_tool_names: list[str]
  · denied_agent_tool_names: list[str]
```

Resolution order:

1. Start with `node_tools`.
2. If `include_agent_tools=none`, include no outer SDK Agent tools.
3. If `selected`, include outer tools whose names are in `allowed_agent_tool_names`.
4. If `all`, include all outer tools except those in `denied_agent_tool_names`.
5. Deny wins over allow when a tool name appears in both lists.

## NodeStreamPolicy

```text
NodeStreamPolicy
  · visible_to_user: bool = true
  · emit_internal_events: bool = configurable
  · include_node_metadata: bool = true
  · final_response_only: bool = false
```

When `stream=True`, LLM/tool events from every node are streamable to the caller.
When `final_response_only=True`, intermediate node LLM/tool events are suppressed from
the user-visible stream and only `TinyCUAResponseNode` final-response events are emitted.
Lifecycle events remain governed by `emit_internal_events`.

## NodeRetryPolicy

```text
NodeRetryPolicy
  · max_attempts: int = 3
  · required_tool_calls: list[str] = []
  · required_output_schema: dict | type[StateObject] | None = None
  · validation_fn: Callable[[LLMResult], ValidationResult] | None = None
  · retry_continuation_builder: Callable[[ValidationError, int], str] | None = None
  · on_retry_exhausted: Literal["raise", "record_failure", "route_failure"] = "record_failure"
```

Retry prompts are assistant-role continuations. Exhaustion behavior:

- `raise`: raise a node execution error to the loop
- `record_failure`: write failure state to the node session and propagate according to
  `PropagationRule.failure`
- `route_failure`: call the node's failure route from `on_complete()` when defined;
  otherwise behave like `record_failure`

## Per-Node Configs

| Config | Additional fields beyond `NodeConfigBase` |
|--------|--------------------------------------------|
| `TinyCUAQueryAnalystNodeConfig` | `allowed_labels: list[str] = ["passthrough", "worker"]`; `classification_schema: dict | None` |
| `TinyCUAInformationDigesterNodeConfig` | `retrieval_enabled: bool = true`; `max_digest_sources: int | None`; `digest_schema: dict | None` |
| `TinyCUAWorkerNodeConfig` | `worker_labels: list[str]`; `allow_passthrough_when_child_exists: bool = true`; `deterministic_prechecks: bool = true` |
| `TinyCUATaskAnalyzerNodeConfig` | `allow_task_create: bool = true`; `allow_task_recreate: bool = true`; `task_schema: dict | None` |
| `TinyCUATaskAssessorNodeConfig` | `assessment_schema: dict | None`; `allow_task_updates: bool = true` |
| `TinyCUATaskExecutorNodeConfig` | `execution_schema: dict | None`; `allow_outer_tools: bool = true` |
| `TinyCUAResultReviewerNodeConfig` | `review_labels: list[str] = ["accept", "retry", "replan", "open_question"]`; `review_schema: dict | None` |
| `TinyCUAResultAggregationNodeConfig` | `aggregation_schema: dict | None`; `max_task_depth: int | None` |
| `TinyCUAResponseNodeConfig` | `allow_information_digest_request: bool = true`; `final_response_schema: dict | None` |

## Related

- [`../loops/node.md`](../loops/node.md)
- [`session_config.md`](session_config.md)
