# TinyCUA Nodes

> **Package:** `tinycua.loops.node`
> **Status:** Target architecture

## Hierarchy

```text
Node
├── DecisionNode
│   ├── TinyCUAQueryAnalystNode
│   └── TinyCUAWorkerNode
└── ProcessNode
    ├── TinyCUAInformationDigesterNode
    ├── TinyCUATaskAnalyzerNode
    ├── TinyCUATaskAssessorNode
    ├── TinyCUATaskExecutorNode
    ├── TinyCUAResultReviewerNode
    └── TinyCUAResponseNode
```

Concrete nodes are TinyCUA-specific classes. Each may have its own config dataclass,
instruction constants, continuation constants, retry policy, message strategy, tool
scope, stream policy, and propagation rule.

## System Prompt Categories

Nodes build LLM input from structured prompt parts:

```text
SystemPromptBundle
  · static_instruction                 # hardcoded node contract
  · configurable_instruction_append    # append-only customization
  · dynamic_system_context             # optional; generally avoided
```

Preferred rendering when supported by the provider/SDK path is multiple system messages:

```text
[
  {"role": "system", "content": static_instruction},
  {"role": "system", "content": configurable_instruction_append},
  {"role": "system", "content": dynamic_system_context},
  ...conversation messages...
]
```

TinyCUA should keep the parts structured internally. If a provider needs one system
message, merge at render time without relying on parsing separators back out of the text.
Most dynamic context should be assistant-role context/continuation, not system prompt.

## Node Contract

```text
Node
  · node_id: str
  · session: Session | None
  · parent: Node | None
  · config: NodeConfigBase
  · is_terminal: bool
  · ensure_session(root_or_parent_session)
  · build_instruction(override_instructions?)
  · build_messages(input: NodeInputLike)
  · validate_output(response)
  · build_retry_continuation(error)
  · record_output(response)
  · propagate()
  · on_complete(queue, response)
```

## Input

Nodes accept:

```text
NodeInputLike = str | NodeInput | NodePayload | list[dict]
```

External strings become user-role messages. Internal strings become assistant-role
messages. `NodeInput` and `NodePayload` are trusted internal objects; user strings are
not parsed as structured internal input.

## TinyCUAResponseNode

`TinyCUAResponseNode` is TinyCUA's final response/synthesis node. It derives from
`ProcessNode`; it is not a generic `PrimaryNode`. It may suspend itself to request
`TinyCUAInformationDigesterNode` and then resume.

## Retry

Node retry behavior is policy-driven:

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

## Compaction Boundary

Nodes may invoke session compaction when their session context exceeds policy limits.
Compaction produces one assistant-role summary message. The node remains responsible for
building the continuation message used after compaction.

## Related

- [`route_map.md`](route_map.md)
- [`propagation.md`](propagation.md)
- [`../config/node_config.md`](../config/node_config.md)
