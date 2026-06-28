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
    ├── TinyCUATaskCreateNode
    ├── TinyCUATaskAnalyzerNode
    ├── TinyCUAAnalysisEffortNode
    ├── TinyCUATaskAssessorNode
    ├── TinyCUATaskExecutorNode
    ├── TinyCUAResultReviewerNode
    ├── TinyCUAResultAggregationNode
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
  {"role": "user", "content": "External user query when selected for this node call."},
  {"role": "assistant", "content": "Relevant prior task context ..."},
  {"role": "assistant", "content": "I will now execute the active task."},
]
```

External user messages come from SDK input merged into root/session context or explicit
`NodeInput`. They are not recreated as user messages for internal node handoffs.

Dynamic system context is limited to node-built high-priority execution constraints:
current active task, node-local state needed for correctness, output schema reminders,
active tool policy, and safety/termination constraints. Descriptive context, summaries,
handoffs, retries, and ordinary continuations MUST be assistant-role messages, not system
prompt fragments.

## Input

Nodes accept:

```text
NodeInputLike = str | NodeInput | NodePayload | list[dict]
```

External strings become user-role messages. Internal strings become assistant-role
messages. `NodeInput` and `NodePayload` are trusted internal objects; user strings are
not parsed as structured internal input. See [`../models/state_object.md`](../models/state_object.md)
for model fields and conversion rules.

## Node Contract

`NodeContract` is a declarative frozen dataclass (FR-064) that captures a node's
execution intent up front, decoupled from runtime mutation:

```text
NodeContract (frozen dataclass, FR-064)
  · goal: str
  · success_criteria: list[str]
  · tool_rationale: dict[str, str]   # tool name → why it is allowed/needed
```

`NodeProgress` tracks live execution progress per node on
`session.node_progress[node_id]` (FR-062), separate from the node contract:

```text
NodeProgress (FR-062)
  · attempts: int
  · last_error: str | None
  · accumulated_tool_results: list[dict]
  · state: Literal["pending", "running", "revising", "done", "failed"]
```

The node itself remains the runtime unit:

```text
Node
  · node_id: str
  · session: Session | None
  · parent: Node | None
  · config: NodeConfigBase
  · contract: NodeContract        # FR-064
  · is_terminal: bool
  · ensure_session(root_or_parent_session)
  · build_instruction(override_instructions?)
  · build_messages(root_session: Session, input: NodeInputLike)
  · validate_output(response)
  · build_retry_continuation(error)
  · record_output(response)
  · propagate()
  · on_complete(queue, response)
```

## TinyCUAResponseNode

`TinyCUAResponseNode` is TinyCUA's final consolidated continuation/synthesis node. It
derives from `ProcessNode`; it is not a generic `PrimaryNode`. It may suspend itself to
request `TinyCUAInformationDigesterNode` and then resume.

Its LLM input is built primarily from accumulated root/session_context plus the latest
propagated node output. It may maintain a session for audit/todo/tool execution, but its
message policy treats it as a continuation of the current TinyCUA session.

On every call, `ResponseNode` first analyzes whether available context is sufficient:
- If sufficient, answer.
- If insufficient, use allowed tools directly or request information digestion if enabled.

## TinyCUAResultAggregationNode

`TinyCUAResultAggregationNode` is a `ProcessNode` entered only after the root task is
accepted/done. It traverses the root task tree, inspects each task context/result/artifacts
reviewer decisions, consolidates information, and emits response-ready context for
`ResponseNode`.

### Responsibility Separation

#### ResultReviewer responsibilities

```text
ResultReviewer:
  - review executor output
  - decide approved / needs_revision / rejected / replan
  - update active TaskResult
  - update active task context
  - trigger task-tree transition
```

#### ResultAggregationNode responsibilities

```text
ResultAggregationNode:
  - entered only after root task is accepted/done
  - traverse the root task tree
  - inspect each task context/result/artifacts/reviewer decisions
  - consolidate information
  - summarize until aggregation is complete
  - emit response-ready context for ResponseNode
```

#### ResponseNode responsibilities

```text
ResponseNode:
  - synthesize/present the user-facing answer from aggregated context
```

### AggregatedResult Model

```text
AggregatedResult
  · root_task_id: str
  · task_summaries: list[str]
  · accepted_results: list[TaskResult]
  · artifacts: list[dict]
  · final_context: str
  · response_continuation: str
  · metadata: dict
```

### Flow (FR-067 state-driven queue)

Queue shape is state-driven, not label-driven:

```text
TaskExecutor → ResultReviewer

  no result yet:
    → [TaskExecutor, ResultReviewer]
  has result, no negative review:
    → [ResultReviewer] only
  has result + needs_revision / rejected:
    → [TaskExecutor, ResultReviewer]
  failed result:
    → [TaskExecutor, ResultReviewer]
  approved + root task done:
    → [ResultAggregationNode]
      → ResponseNode
  replan:
    → TaskAssessor(scope=active_task_or_local_region)
    → TaskAnalyzer(mode=local_replan, init_enabled=false)
    → TaskExecutor
  approved-but-not-completed (FR-079 safety net):
    → re-open task, clear approval, requeue [TaskExecutor, ResultReviewer]
```

### ResultReviewer Replan Separation

ResultReviewer replan is a local execution-time recovery path, NOT a full upfront
planning process. The replan path MUST NOT spawn `AnalysisEffortNode` and MUST NOT
run the Worker-owned effort-gated upfront TaskAnalysisLoop.

```text
Worker-owned task_creation/recreation/reanalysis:
  TaskCreate or TaskAnalysis
  → AnalysisEffortNode
  → optional repeated [TaskAssessor, TaskAnalysis]
  → TaskExecutor

ResultReviewer replan:
  TaskAssessor(scope=active_task_or_local_region)
  → TaskAnalyzer(mode=local_replan, init_enabled=false)
  → TaskExecutor
```

Worker effort planning is configurable and can perform multiple global decomposition
passes. Reviewer replan is narrowly scoped to the current active task or local task
region and does not include `AnalysisEffortNode`.

## Retry

Node retry behavior is policy-driven by the retry policy defined in
[`../config/node_config.md`](../config/node_config.md). Retry prompts are assistant-role
continuations.

## Todo

Every TinyCUA node session MUST have a Todo. Todo tools are generic node tools available to all TinyCUA nodes unless disabled by `NodeToolPolicy`. Nodes SHOULD structure their
work through Plan -> Analyze -> Act, using Todo as the local step tracker. Task is the
broader session goal; Todo is the smaller local execution driver. Every node's session
provides access to a Todo so the node can plan then execute in a structured manner.

## Compaction Boundary

Nodes invoke compaction through `session.compact_context()` when
`len(session.session_context)` or estimated context tokens exceed `SessionConfig` limits.
The session delegates to `session.session_config.compaction_strategy.compact(messages)`.

Compaction produces one assistant-role summary message and replaces only the selected
`session_context` window; `chat_history` remains an audit trail and is not destructively
compacted. The node that requested compaction remains responsible for building the
assistant-role continuation message used after compaction.

## Related

- [`route_map.md`](route_map.md)
- [`propagation.md`](propagation.md)
- [`../config/node_config.md`](../config/node_config.md)
