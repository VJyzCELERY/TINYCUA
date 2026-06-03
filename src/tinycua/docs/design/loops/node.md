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

Nodes build LLM input from structured prompt fragments managed through
`SystemPrompt` / `SystemPromptBuilder`. Fragments are kept distinct internally and
rendered into **one final system-role message** for the actual LLM call.

```text
SystemPrompt
  · priority: int
  · kind: "static" | "configurable" | "dynamic"
  · content: str
  · metadata: dict

SystemPromptBuilder
  · fragments: list[SystemPrompt]
  · add_static(content)               # hardcoded node contract
  · add_configurable_append(content)  # append-only customization
  · add_dynamic_context(content)      # optional node-built instruction/context
  · build() → {"role": "system", "content": ordered_merged_content}
```

Internal fragments are ordered by explicit priority. The final LLM call receives one
system dict followed by conversation/continuation messages:

```text
[
  SystemPromptBuilder([
    SystemPrompt(kind="static", content=constant_node_instruction),
    SystemPrompt(kind="configurable", content=configurable_instruction_append),
    SystemPrompt(kind="dynamic", content="Current active task: T-0.1 ..."),
  ]).build(),
  {"role": "assistant", "content": "Relevant prior task context ..."},
  {"role": "assistant", "content": "I will now execute the active task."},
]
```

Dynamic system context is allowed for node-built high-priority execution constraints
such as current active task, node-local state, output schema reminders, or active tool
policy. Most descriptive context should still be assistant-role context/continuation, not
system prompt.

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

## Todo

Every node has access to its session's `Todo` — a small, isolated, linear, non-complex
todo list. Nodes may read, check off, and extend the list to operate in a plan-then-execute
manner. Todo is per-session and does not span across sessions. The global parent session
`Task` is the overall goal; Todo is the local step-by-step execution plan.

## Compaction Boundary

Nodes may invoke session compaction when their session context exceeds policy limits.
Compaction produces one assistant-role summary message. The node remains responsible for
building the continuation message used after compaction.

## Related

- [`route_map.md`](route_map.md)
- [`propagation.md`](propagation.md)
- [`../config/node_config.md`](../config/node_config.md)
