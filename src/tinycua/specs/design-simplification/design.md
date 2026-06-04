# Design Document: TinyCUA Design Simplification — Documentation Reorganization

**Spec**: [./spec.md](./spec.md)
**Status**: In Progress
**Last Updated**: 2026-06-04

---

## Overview

This design reorganizes `src/tinycua/docs/design/` around a simplified TinyCUA runtime model that builds on, not around, the current `tinycua-sdk` contract. The target architecture is one SDK `Agent` configured with `TinyCUALoop`, where `TinyCUALoop` extends SDK `BaseLoop`, processes a sequential `NodeQueue`, and runs concrete TinyCUA-specific nodes. The design preserves useful existing graph/session behavior — propagation, task sharing, passthrough, retry, and streaming — while removing the target concepts of `AgentGraph`, `RouterNode`, `AgentNode`, worker QueryAnalyst, per-agent loops, and generic `PrimaryNode`.

This PR is documentation-only. It reorganizes design docs and creates a reviewable roadmap issue draft. It does not implement the runtime.

---

## Document Authority / Source of Truth

This file is the blueprint and design-decision record for the design-simplification PR.
`src/tinycua/docs/design/` is the refined implementation-facing target design. Refined
docs may add detail, specialize examples, or clarify implementation contracts as long as
they preserve the same semantics. Treat a difference as an issue only when it creates
incompatible implementation behavior, contradicts a MUST-level design decision, duplicates
competing sources of truth, or leaves the canonical implementation contract ambiguous.

---

## Current Architecture Problem

Current docs describe a layered graph system:

```text
AgentGraph / Orchestrator
  → RouterNode / InputGate
  → AgentNode
  → SDK Agent
  → Agent-specific AgentLoop
```

This creates duplicated concepts across graph, node, agent, loop, state, and config docs. It also makes worker behavior appear as a nested graph with its own QueryAnalyst input gate.

The new docs should describe the same TinyCUA capabilities through one SDK-compatible loop and a sequential queue.

---

## Proposed Architecture

```text
SDK Agent
└── TinyCUALoop extends SDK BaseLoop
    ├── root Session
    │   ├── session_context
    │   ├── chat_history
    │   ├── task / todo state
    │   └── SessionConfig
    └── NodeQueue
        ├── TinyCUAQueryAnalystNode        : DecisionNode
        ├── TinyCUAInformationDigesterNode : ProcessNode
        ├── TinyCUAWorkerNode              : DecisionNode
        ├── TinyCUATaskAnalyzerNode        : ProcessNode
        ├── TinyCUATaskAssessorNode        : ProcessNode
        ├── TinyCUATaskExecutorNode        : ProcessNode
        ├── TinyCUAResultReviewerNode      : ProcessNode
        └── TinyCUAResponseNode            : ProcessNode, terminal/suspendable
```

This is a TinyCUA-specific migration of the current graph/node system, not a generic node framework.

### Component Overview

| Component | Role | Replaces / Simplifies |
|-----------|------|-----------------------|
| `TinyCUALoop` | SDK-compatible loop that owns queue execution. | AgentGraph + per-agent AgentLoops |
| `NodeQueue` | Sequential queue; `queue[0]` is active. | GraphQueue + nested subgraph queues |
| `Node` | Base for TinyCUA-specific node classes. | BaseAgentNode wrapper layer |
| `DecisionNode` | Makes decisions and dispatches routes. | QueryAnalyst input gates + RouterNode |
| `ProcessNode` | Performs scoped work and produces output. | Individual AgentNodes/AgentLoops |
| `RouteMap` | DecisionNode-owned label-to-handler dispatch table. | RouterNode |
| `NodeInput` / `NodePayload` | Trusted internal transport. | YAML/front-matter string transport |
| `TinyCUAResponseNode` | TinyCUA final response node. | PrimaryAgent target concept |

---

## SDK Contract Boundary

TinyCUA must build around the current SDK contract:

```text
Agent.run(query, messages=None, instructions=None, stream=False, file_attachments=None)
  → builds user message
  → msgs = (messages or []) + [user_msg]
  → loop.run(agent, msgs, agent.tools, instructions, stream=stream)
```

`TinyCUALoop.run(...)` receives:

```text
agent: SDK Agent
messages: list[dict]                  # SDK-provided messages + current user message
tools: list[Tool]                      # outer Agent(tools=[...])
override_instructions: str | None      # SDK instructions override
stream: bool
```

Design rules:

1. Do not modify SDK APIs.
2. Treat SDK-provided `messages` as input context to merge/record according to TinyCUA session policy with dedupe.
3. Treat SDK-provided `tools` as the outer tool pool; expose them per node through `NodeToolPolicy`.
4. Acknowledge `override_instructions`, but preserve TinyCUA node contracts through hardcoded node instructions plus append-only customization.
5. Preserve SDK streaming behavior: `stream=True` returns an async iterator; `stream=False` returns the final string.
6. If a SDK override parameter is not fully specified in TinyCUA docs yet, preserve compatibility and treat it conservatively rather than implying SDK changes.

### System Message Compatibility

The SDK canonical message type supports `{"role": "system", "content": ...}`. Current OpenAI Chat Completions and Responses translators pass system messages through. TinyCUA MUST send **one final system message** to each LLM call for provider portability and deterministic prompt layout.

TinyCUA MUST keep an internal structured representation of system prompt parts through `SystemPrompt` / `SystemPromptBuilder` instead of relying on parsing rendered system text back into parts. `build_messages()` renders the fragments into one ordered system-role message at the LLM boundary.

---

## TinyCUALoop

`TinyCUALoop` extends SDK `BaseLoop`. It uses `agent._call_llm(...)` for node LLM calls and does not create separate SDK Agent instances per node by default.

### Queue Bootstrap and Continuation Routing

Every `TinyCUALoop.run(...)`:

1. Merge SDK messages into root session input context.
2. Prepend or ensure `TinyCUAQueryAnalystNode` as the run entry node.
   - If `QueryAnalyst` is already current from an interrupted run, do not duplicate it.
3. Ensure a terminal node exists at the end of the queue.
   - If an existing terminal path exists, do nothing.
   - If no terminal path exists, append default `TinyCUAResponseNode`.

### QueryAnalyst Prechecks

Before LLM classification, `TinyCUAQueryAnalystNode` runs deterministic prechecks:

1. If a valid `mandatory_passthrough` exists, forward the user continuation to the target node/session.
2. If an existing `WorkerNode` is already queued before the terminal `ResponseNode` when routing to `worker`, do not spawn a new `WorkerNode`; forward/assign the current `NodeInput` to the existing `WorkerNode` and advance/remove `QueryAnalyst`.
3. If no valid mandatory passthrough exists and no existing WorkerNode reuse applies, run normal `QueryAnalyst` LLM classification.

### Mandatory Passthrough

`mandatory_passthrough` is a deterministic continuation directive available to every node:

```text
MandatoryPassthrough
  · target_node_id: str
  · target_session_id: str | None        # stale-continuation guard (expected active session)
  · reason: str
  · payload: NodeInput | NodePayload | None
  · allow_query_analyst_restart: bool = true
```

`target_session_id` is the expected active session for `target_node_id`. If present and
the target node has a different current session id, the passthrough is stale/invalid and
falls back according to `allow_query_analyst_restart` (see `loops/route_map.md`).

When `QueryAnalyst` encounters a valid `mandatory_passthrough`:
- Forward the user continuation to the target node/session.
- Do not run LLM classification.
- If `allow_query_analyst_restart` is true and the target is no longer valid, fall back to normal classification.

### TaskTree and Active Task Lifecycle

Active task selection uses DFS pre-order traversal of the root Task tree:

```text
TinyCUALoop.get_active_task() -> Task | None
TinyCUALoop.set_active_task(task_id) -> None
TinyCUALoop.update_active_task_result(...)
```

Active task is resolved by DFS pre-order traversal of the root Task tree. The first unfinished task matching the active-task predicate is selected. `active_child_id` is a traversal hint maintained by the loop.

### TaskTree Completion/Update Rules

On `ResultReviewer` accept:

```text
on_result_reviewer_accept(active_task):
  1. Mark current task result as accepted.
  2. Update active task context/result.
  3. If current task is complete, go up to parent.
     - If no parent exists, root task is done; route to ResultAggregationNode.
  4. If current task is unfinished, DFS pre-order to the next unfinished child.
  5. If no unfinished child exists:
     - If current task has no children, execute current task.
     - If all children are complete, re-evaluate current task completion.
       - If complete, mark complete and continue upward.
       - If incomplete, update task instruction/context with remaining criteria and execute current task.
```

### ResultAggregationNode

`TinyCUAResultAggregationNode` is a `ProcessNode` entered only after the root task is accepted/done:

```text
TaskExecutor
  → ResultReviewer
      accept
        → task-tree update
        → if root task done:
             ResultAggregationNode
             ResponseNode
      retry
        → TaskExecutor
      replan
        → TaskAnalyzer
      open_question
        → mandatory_passthrough to ResultReviewer
```

`ResultAggregationNode` traverses the root task tree, inspects each task context/result/artifacts/reviewer decisions, consolidates information, and emits response-ready context for `ResponseNode`.

### ResponseNode Consolidated Continuation

`TinyCUAResponseNode` is the final consolidated continuation/synthesis node. Its LLM input is built primarily from accumulated root/session_context plus the latest propagated node output. It may maintain a session for audit/todo/tool execution, but its message policy treats it as a continuation of the current TinyCUA session.

On every call, `ResponseNode` first analyzes whether available context is sufficient.
- If sufficient, answer.
- If insufficient, use allowed tools directly or request information digestion if enabled.

### Provider Prompt Caching Non-Goal

TinyCUA context management may interact with provider prompt caching in provider-specific ways. This design does not optimize provider cache hit rates, cost, or speed. The primary goal is context quality and better model output.

### Execution Flow

```text
TinyCUALoop.run(agent, messages, tools, override_instructions, stream):
  1. Merge SDK messages into root session input context according to session policy.
  2. Prepend or ensure TinyCUAQueryAnalystNode as the run entry node.
     - If QueryAnalyst is already current from an interrupted run, do not duplicate it.
  3. Ensure a terminal node exists at the end of the queue.
     - If an existing terminal path exists, do nothing.
     - If no terminal path exists, append default TinyCUAResponseNode.
  4. While queue is not empty:
        node = queue.current
        node_session = node.ensure_session(...)
        node_input = queue.input_for_current()
        input_messages = node.build_messages(root_session, node_input)
        instructions = node.build_instruction(override_instructions)
        scoped_tools = node.tool_policy.resolve(node_tools, outer_agent_tools=tools)
        result = call/stream agent._call_llm(input_messages, scoped_tools)
        validate/retry according to node retry policy
        record chat history and selected session context
        node.on_complete(queue, result)
  5. Return final TinyCUAResponseNode string or stream events.
```

---

## NodeQueue

`NodeQueue` is the execution structure. `queue[0]` is the active node. Queue order determines execution order only; it does not automatically share context.

```text
NodeQueue
  · items: list[Node]
  · current → Node | None
  · input_for_current() → NodeInputLike
  · advance() → Node | None
  · spawn_after_current(nodes) → None
  · suspend_current_and_prepend(nodes) → None
  · clear_after_current() → None
  · ensure_terminal(default_response_node) → None
  · is_empty() → bool
```

### Suspension and Prepend

Suspension is queue-position based. No dedicated persisted suspended state is required.

```text
Before:
  [TinyCUAResponseNode(active)]

TinyCUAResponseNode requests more information:
  suspend_current_and_prepend([TinyCUAInformationDigesterNode(parent=TinyCUAResponseNode)])

After:
  [TinyCUAInformationDigesterNode(active), TinyCUAResponseNode(suspended)]

Digester completes and propagates to parent:
  [TinyCUAResponseNode(active/resumed)]
```

This is a general queue capability. The first intended use case is `TinyCUAResponseNode` requesting information digestion.

---

## Node Hierarchy

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
    ├── TinyCUAResultAggregationNode
    └── TinyCUAResponseNode
```

Each concrete node is TinyCUA-specific and may have its own config dataclass, instruction constants, continuation constants, retry policy, tool policy, stream policy, message strategy, and propagation rule.

---

## DecisionNode and RouteMap

`DecisionNode` makes a decision, validates the label, then dispatches to a named handler through its `RouteMap`.

```text
RouteMap
  · routes: dict[str, Route]

Route
  · label: str
  · handler: Callable[[NodeQueue, DecisionResult], None]

DecisionResult
  · label: str
  · confidence: float | None
  · rationale: str | None
  · raw_output: str | dict | None
  · metadata: dict
```

RouteMap is not an independent orchestration layer. It is owned by concrete DecisionNode classes.
`DecisionResult.label` is validated against `RouteMap.routes` before dispatch.

```text
TinyCUAQueryAnalystNode.route_map:
  passthrough → route_passthrough()
  worker      → route_worker()

TinyCUAWorkerNode.route_map:
  task_recreation   → route_task_recreation()
  task_reanalysis   → route_task_reanalysis()
  passthrough       → route_passthrough()
  proceed_execution → route_proceed_execution()
```

---

## Worker Decision Model

There is no separate worker QueryAnalyst in the target architecture. Worker-specific QueryAnalyst behavior is folded into `TinyCUAWorkerNode`.

```text
TinyCUAWorkerNode enters

1. Does task exist?
   ├── No
   │   → spawn TinyCUATaskAnalyzerNode with TaskInit/TaskCreate tools
   │   → WorkerNode calls `queue.advance()` and does not re-insert itself
   └── Yes
       → continue

2. Are worker-spawned nodes queued/active?
   ├── Yes
   │   → call Worker LLM decision with labels:
   │       task_recreation, task_reanalysis, passthrough, proceed_execution
   └── No
       → call Worker LLM decision without passthrough:
           task_recreation, task_reanalysis, proceed_execution
```

Passthrough is available only when there is a worker-spawned node to receive the forwarded query/context.

---

## TinyCUAResponseNode

`TinyCUAResponseNode` is TinyCUA's final consolidated continuation/synthesis node. It derives from `ProcessNode`; it is not a generic `PrimaryNode` primitive.

Its LLM input is built primarily from accumulated root/session_context plus the latest propagated node output. It may maintain a session for audit/todo/tool execution, but its message policy treats it as a continuation of the current TinyCUA session.

On every call, `ResponseNode` first analyzes whether available context is sufficient:
- If sufficient, answer.
- If insufficient, use allowed tools directly or request information digestion if enabled.

It may also suspend itself to request `TinyCUAInformationDigesterNode`:

```text
ResponseNode session_context
  → NodeInput(messages=response_node.session_context, payloads=[InformationDigestRequest])
  → InformationDigesterNode(parent=ResponseNode)
  → digest result propagates back to ResponseNode
  → ResponseNode resumes final synthesis
```

### ResultAggregationNode

`TinyCUAResultAggregationNode` is a `ProcessNode` entered only after the root task is accepted/done. It traverses the root task tree, inspects each task context/result/artifacts/reviewer decisions, consolidates information, and emits response-ready context for `ResponseNode`.

Responsibilities:

```text
ResultReviewer:
  - review executor output
  - decide accept/retry/replan/open_question
  - update active TaskResult
  - update active task context
  - trigger task-tree transition

ResultAggregationNode:
  - entered only after root task is accepted/done
  - traverse the root task tree
  - inspect each task context/result/artifacts/reviewer decisions
  - consolidate information
  - summarize until aggregation is complete
  - emit response-ready context for ResponseNode

ResponseNode:
  - synthesize/present the user-facing answer from aggregated context
```

```text
ResponseNode session_context
  → NodeInput(messages=response_node.session_context, payloads=[InformationDigestRequest])
  → InformationDigesterNode(parent=ResponseNode)
  → digest result propagates back to ResponseNode
  → ResponseNode resumes final synthesis
```

Suspension handoff protocol:

1. `TinyCUAResponseNode` copies a selected subset of its `session_context` into
   `NodeInput(messages=[...])`; it may add an `InformationDigestRequest` payload.
2. The copied input is assigned to the prepended digester node. The digester may read it
   but does not re-store those copied messages as reusable context.
3. The digester propagates selected digest output to its parent response node session.
4. The response node resumes only after the propagated digest is available in its
   `session_context`.

`InformationDigesterNode` is optional and invoked only when direct accumulated context/tool access is insufficient. `ResponseNode` should first evaluate whether accumulated context is enough. `TaskExecutor` should use `enhanced_context_retrieval` directly instead of spawning `InformationDigesterNode`.

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

### Enhanced Context Retrieval Cache Behavior

`enhanced_context_retrieval` is a tool available to `InformationDigesterNode`, `TaskExecutor`, and `ResponseNode`:

```text
enhanced_context_retrieval:
  - Receives the current session or selected session_context.
  - Lazily creates a scoped context cache file when called.
  - The cache contains only selected context for that session/tool call.
  - Retrieval runs as a ReAct-style search over the cache.
  - Search/read tools are limited to grep/search within the cache and paginated cache reads.
  - InformationDigesterNode may call the tool, but the tool owns cache creation.
```

---

## NodeInput and NodePayload

Nodes accept:

```text
NodeInputLike = str | NodeInput | NodePayload | list[dict]
```

`NodeInput` and `NodePayload` use `StateObject`-style serialization, but are not `AgentState`. `AgentState` remains node lifecycle/result state; `NodeInput`/`NodePayload` are internal transport.

```text
NodePayload <: StateObject
  · payload_type: str
  · source_node: str | None
  · content: str | dict | StateObject | list[dict]
  · metadata: dict
  · to_message() → {"role": "assistant", "content": formatted_string}
  · to_messages() → list[dict]

NodeInput <: StateObject
  · input_type: str
  · source_node: str | None
  · target_node: str | None
  · messages: list[dict]
  · payloads: list[NodePayload]
  · metadata: dict
  · to_messages() → list[dict]
```

String fallback:

```text
external user string → {"role": "user", "content": query}
internal string      → {"role": "assistant", "content": text}
```

Normal internal communication should not rely on YAML/front-matter parsing. Only queue-created internal objects are trusted as structured node input.

---

## Node Sessions and Context

Each node manages its own session/message context. A node session may be fresh, inherited, reused, scoped from parent/root, or enhanced through retrieval tools.

Parent reference controls lineage and propagation target. It does not automatically mean full context inheritance.

```text
chat_history    = audit trail of user input, node output, tool calls, retries, and internal communication
session_context = selected, deduped LLM-reusable messages
```

Messages passed as node input are not automatically re-stored. Nodes store new outputs and selected reusable context according to propagation/persistence policy.

## Task and Todo

A `Task` is the global parent session overall goal — the high-level objective of an entire session. It lives at the root session level and is not duplicated per node.

A `Todo` is a small, isolated, linear, non-complex todo list stored per session. Every TinyCUA node session MUST have a Todo. Todo tools are generic node tools available to all TinyCUA nodes unless disabled by `NodeToolPolicy`. Nodes SHOULD structure their work through Plan -> Analyze -> Act, using Todo as the local step tracker. Task is the broader session goal; Todo is the smaller local execution driver.

```text
Task   → global parent session goal (one per root session)
Todo   → per-session linear todo list (one per session, node-scoped)
```

Example execution flow using Todo:

```text
TinyCUATaskExecutorNode.ensure_session()
  → session.todo = [
      "Read relevant file contents",
      "Implement the requested change",
      "Run tests to verify",
    ]
  → node reads first item, executes it, marks it done
  → node reads second item, executes it, marks it done
  → ...
```

Nodes are not required to use Todo, but every node's session provides access to one. The node itself decides whether to populate, read, or ignore it.

---

## System Prompt Construction

Node message construction MUST keep system prompt categories distinct internally and render them into one system message for the actual LLM call:

```text
SystemPrompt
  · priority: int
  · kind: "static" | "configurable" | "dynamic"
  · content: str
  · metadata: dict

SystemPromptBuilder
  · fragments: list[SystemPrompt]
  · add_static(content)
  · add_configurable_append(content)
  · add_dynamic_context(content)
  · build() → {"role": "system", "content": ordered_merged_content}
```

Internal fragments are ordered by explicit priority. The final LLM call receives one system dict followed by conversation/continuation messages:

```text
[
  SystemPromptBuilder([
    SystemPrompt(kind="static", content=constant_node_instruction),
    SystemPrompt(kind="configurable", content=configurable_instruction_append),
    SystemPrompt(kind="dynamic", content="Current active task: T-0.1 ..."),
  ]).build(),
  {"role": "user", "content": external_user_query},                  # only actual user input
  {"role": "assistant", "content": previous_node_result},            # internal context
  {"role": "assistant", "content": continuation_prompt},             # internal continuation
]
```

Dynamic system context is allowed when a node needs to provide high-priority execution
constraints such as current active task, active tool policy, output schema reminder, or
node-local state that should be interpreted as instruction rather than conversation.
Most descriptive context should still be passed as assistant-role context/continuation so
it can be audited, propagated, and compacted consistently.

The session/history layer may store prompt fragments or metadata separately for audit and debugging. The LLM-bound `build_messages()` helper is responsible for rendering exactly one system prompt message so prompt structure remains internal and provider-portable.

---

## Message Role Policy

Only actual external user input uses role `user`.

All internal TinyCUA LLM calls are assistant-role continuations, including:

- node handoffs
- continuation prompts
- retry prompts
- validation correction prompts
- monitor-generated continuations

Tool messages may use provider-required tool roles. System instructions remain system messages.

---

## Instruction and Continuation Construction

Customization is append-only by default.

```text
final_instruction =
  hardcoded_node_instruction_constant
  + optional configurable_node_instruction_append

final_continuation =
  hardcoded_node_continuation_constant
  + optional configurable_node_continuation_append

final_retry_continuation =
  hardcoded_node_retry_constant
  + optional configurable_retry_append
```

Hardcoded constants preserve TinyCUA's required behavior. Append-only configuration lets users tailor behavior without removing node contracts.

---

## CompactionStrategy

Compaction is selected by `SessionConfig`, but the compaction class owns compaction behavior and configuration.

```text
CompactionStrategy
  · compact(messages: list[dict]) → dict
```

Contract:

1. Input is a list of message dicts, normally from `session_context` or a node-selected subset of context.
2. Output is exactly one assistant-role message:

   ```text
   {"role": "assistant", "content": "<summary of compacted context>"}
   ```

3. Compaction summarizes context only. Continuation prompts remain the responsibility of the node that resumes after compaction.
4. Compaction excludes system-role messages by default. The caller/node decides what context to pass to the strategy.
5. A strategy MAY include its own internal Agent or non-agent summarization logic. This is the explicit exception to the TinyCUALoop rule that the loop does not create internal Agents for normal node execution.
6. `SessionConfig` dictates which strategy is used; the strategy class is the authority for its own model/tool/instruction/config details.
7. `Session.compact_context(window: list[dict] | None = None) -> dict | None` selects or accepts a compactable context window, calls the strategy, replaces that `session_context` window with the returned assistant summary, and returns the summary.

Example node-selected compaction input:

```text
node_context = [m for m in session.session_context if m["role"] != "system"]
summary_msg = session.session_config.compaction_strategy.compact(node_context)
session.session_context = [summary_msg]
```

### SimpleCompaction

`SimpleCompaction` is the default/simple strategy implementation.

```text
SimpleCompaction extends CompactionStrategy
```

Behavior:

1. Receive a parent SDK Agent configuration snapshot during `create_tinycua_agent(...)` or
   session setup where available, especially language model and provider configuration.
2. Use a documented default fallback configuration when no parent Agent/config is
   available.
3. Run a small tool-less compaction Agent. It receives the selected session messages as
   its message context.
4. Its instruction/system prompt states that it is a compaction agent.
5. Its continuation prompt asks it to summarize the session context into a compact,
   reusable summary.
6. It exposes no tools.
7. It returns the final response as the compaction output:

   ```text
   {"role": "assistant", "content": response}
   ```

`SimpleCompaction` still follows the general strategy rule: it compacts context only.
The node that requested compaction remains responsible for any continuation prompt after
the compacted assistant summary is inserted back into `session_context`.

---

## Retry and Validation

Node retry remains part of the architecture.

```text
NodeRetryPolicy
  · max_attempts: int = 3
  · required_tool_calls: list[str] = []
  · required_output_schema: dict | type[StateObject] | None = None
  · validation_fn: Callable[[LLMResult], ValidationResult] | None = None
  · retry_continuation_builder: Callable[[ValidationError, int], str] | None = None
  · on_retry_exhausted: Literal["raise", "record_failure", "route_failure"] = "record_failure"
```

The loop owns mechanics: call LLM, stream events, repeat attempts, and log retry continuations. The node owns policy: what is valid, how to retry, and how to handle exhaustion.
On exhaustion, `record_failure` writes failure state to the node session and propagates
according to `PropagationRule.failure`; `route_failure` uses the node's failure route when
defined and otherwise records failure; `raise` raises a loop-visible node error.

---

## Naming Convention: Rule vs Policy vs Strategy

TinyCUA suffixes indicate ownership and behavioral scope:

| Suffix | Meaning | Examples |
|--------|---------|----------|
| `Rule` | Cross-node or cross-session data movement contract. Rules describe what may move across boundaries. | `PropagationRule` |
| `Policy` | Declarative behavior configuration evaluated by a node/session/loop. Policies do not own large algorithms. | `NodeToolPolicy`, `NodeStreamPolicy`, `NodeRetryPolicy`, `NodeMessagePolicy` |
| `Strategy` | Pluggable algorithm or implementation choice that owns behavior details and may have its own configuration. | `CompactionStrategy` |

Use `Policy` for lightweight per-node/session decisions, `Rule` for boundary/propagation
contracts, and `Strategy` when implementations are swappable algorithms.

---

## AgentMonitor / NodeMonitor Consideration

The old AgentMonitor concept remains as an optional transient hook. It is not a durable queue node by default.

Trigger points are before a node LLM call, after a node result before validation/retry,
and after retry exhaustion before failure propagation. Inputs include node/session ids,
attempt number, resolved tools, LLM-bound messages, result or validation error, and stream
mode. The hook may return an assistant-role continuation or no-op. Monitor invocations do
not create sessions and are not written to `chat_history` or `session_context` unless the
owning node explicitly records a derived message under normal recording policy.

---

## PropagationRule

`PropagationRule` preserves the old `Session.terminate_child(...)` behavior while making it explicit/configurable.

```text
PropagationRule
  · chat_history: none | parent | root
  · session_context_target: none | parent | root | parent_and_root
  · session_context_mode: none | final | full | selected
  · token_usage: none | parent | root | parent_and_root
  · failure: none | parent | root | parent_and_root
  · dedupe: bool
```

Profiles:

| Profile | chat_history | session_context_target | session_context_mode | token_usage | failure |
|---------|--------------|------------------------|----------------------|-------------|---------|
| transient_legacy | parent_and_root | none | none | parent_and_root | parent_and_root |
| natural_termination_legacy | parent_and_root | parent_and_root | final | parent_and_root | parent_and_root |
| mid_progress_legacy | parent_and_root | parent_and_root | full | parent_and_root | parent_and_root |
| selected_internal_output | root | root | selected | root | root |

QueryAnalyst and InformationDigester may now propagate selected deduped context to root/parent while preserving full audit in chat history.

---

## Tool Scoping

Each node controls its tool exposure.

```text
NodeToolPolicy
  · node_tools: list[Tool]
  · include_agent_tools: none | selected | all
  · allowed_agent_tool_names: list[str]
  · denied_agent_tool_names: list[str]
```

The outer SDK `Agent(tools=[...])` remains the source of caller-provided tools. TinyCUA chooses which of those tools each node can see.
Deny wins over allow. `selected` includes only named outer tools from
`allowed_agent_tool_names`; `all` includes all outer tools except denied names.

| Node | Tool Scope |
|------|------------|
| TinyCUAQueryAnalystNode | classification + read-only task/context tools |
| TinyCUAInformationDigesterNode | enhanced retrieval + digest tools |
| TinyCUAWorkerNode | worker decision tools only |
| TinyCUATaskAnalyzerNode | task structure tools, optionally TaskInit/TaskCreate |
| TinyCUATaskAssessorNode | task assessment/read/update tools as needed |
| TinyCUATaskExecutorNode | task execution tools + selected outer Agent tools + `enhanced_context_retrieval` + exploration/web/context search tools when enabled |
| TinyCUAResultReviewerNode | review/decision tools |
| TinyCUAResponseNode | same base toolset as TinyCUATaskExecutorNode + final response/synthesis behavior + optional information-digestion request capability only when enabled |

TaskExecutor does not spawn InformationDigesterNode. If TaskExecutor needs more context, it calls `enhanced_context_retrieval` directly.

---

## Streaming / SSE

TinyCUALoop preserves SDK streaming:

```text
stream=True  → async iterator of SSE-compatible event dicts
stream=False → final normalized str from TinyCUAResponseNode
```

When `stream=True`, LLM/tool events from every node should be visible to the caller.

```text
NodeStreamPolicy
  · visible_to_user: bool = true
  · emit_internal_events: bool = configurable
  · include_node_metadata: bool = true
  · final_response_only: bool = false
```

LLM/tool SSE events are visible by default. TinyCUA lifecycle events such as `tinycua.node.started`, `tinycua.node.suspended`, `tinycua.node.resumed`, `tinycua.retry.started`, and `tinycua.queue.updated` are separately controlled by `emit_internal_events`.
When `final_response_only=True`, intermediate node LLM/tool events are suppressed from
the user-visible stream and only `TinyCUAResponseNode` final-response events are emitted;
lifecycle events remain governed by `emit_internal_events`.

---

## Loop Termination

The loop terminates when the queue is empty after terminal response handling.

`TinyCUAResponseNode` is usually the terminal synthesis node. If it suspends itself to gather information, it is not terminal until it resumes and completes final response synthesis.

---

## Documentation Reorganization

Target structure:

```text
docs/design/
├── README.md
├── config/
│   ├── node_config.md
│   └── session_config.md
├── constants/
│   ├── instructions.md
│   └── tools.md
├── loops/
│   ├── overview.md
│   ├── base_loop.md
│   ├── tinycua_loop.md
│   ├── node_queue.md
│   ├── node.md
│   ├── route_map.md
│   ├── propagation.md
│   ├── worker_concept.md
├── models/
├── tools/
└── utility/
```

---

## Migration Table

| Current Path | Disposition | New Owner | Concepts Preserved / Changed |
|-------------|-------------|-----------|-------------------------------|
| `README.md` | update | `README.md` | New reading order and target architecture map. |
| `agent_node/base.md` | merge/delete | `loops/node.md`, `loops/tinycua_loop.md`, `models/session.md` | Node/session contract, instruction caching, monitor consideration; remove SDK Agent wrapper pattern. |
| `agent_node/factory.md` | delete | — | Factory replaced by `create_tinycua_agent(...)` and concrete TinyCUA node construction. |
| `agent_node/query_analyst.md` | merge/delete | `loops/node.md`, `loops/route_map.md` | Becomes `TinyCUAQueryAnalystNode : DecisionNode`; top-level only. |
| `agent_node/information_digester.md` | merge/delete | `loops/node.md`, `tools/digester.md`, `loops/propagation.md` | Becomes `TinyCUAInformationDigesterNode : ProcessNode`; can be prepended by ResponseNode. |
| `agent_node/task_analyzer.md` | merge/delete | `loops/node.md`, `tools/task.md` | Becomes `TinyCUATaskAnalyzerNode`; TaskInit/TaskCreate tool scope documented. |
| `agent_node/task_assessor.md` | merge/delete | `loops/node.md`, `tools/task.md` | Becomes `TinyCUATaskAssessorNode`. |
| `agent_node/task_executor.md` | merge/delete | `loops/node.md`, `tools/task.md`, `config/node_config.md` | Becomes `TinyCUATaskExecutorNode`; selected outer Agent tools allowed. |
| `agent_node/result_reviewer.md` | merge/delete | `loops/node.md`, `loops/worker_concept.md` | Becomes `TinyCUAResultReviewerNode`; open-question behavior preserved. |
| `agent_node/primary_agent.md` | merge/delete | `loops/node.md`, `loops/tinycua_loop.md` | Becomes `TinyCUAResponseNode`; no generic PrimaryNode. |
| `agents/overview.md` | merge/delete | `loops/node.md` | Thin cards folded into concrete TinyCUA node docs. |
| `agents/query_analyst.md` | merge/delete | `loops/node.md` | Covered by `TinyCUAQueryAnalystNode`. |
| `agents/information_digester.md` | merge/delete | `loops/node.md`, `tools/digester.md` | Covered by `TinyCUAInformationDigesterNode`. |
| `agents/task_analyzer.md` | merge/delete | `loops/node.md` | Covered by `TinyCUATaskAnalyzerNode`. |
| `agents/task_assessor.md` | merge/delete | `loops/node.md` | Covered by `TinyCUATaskAssessorNode`. |
| `agents/task_executor.md` | merge/delete | `loops/node.md` | Covered by `TinyCUATaskExecutorNode`. |
| `agents/result_reviewer.md` | merge/delete | `loops/node.md` | Covered by `TinyCUAResultReviewerNode`. |
| `agents/primary_agent.md` | merge/delete | `loops/node.md` | Reframed as `TinyCUAResponseNode`. |
| `orchestration/overview.md` | merge/delete | `loops/overview.md`, `loops/tinycua_loop.md` | AgentGraph overview becomes TinyCUALoop overview. |
| `orchestration/graph_queue.md` | merge/delete | `loops/node_queue.md` | GraphQueue becomes NodeQueue; add suspension/prepend. |
| `orchestration/tinycua.md` | merge/delete | `loops/tinycua_loop.md`, `loops/node.md` | Top-level graph becomes SDK Agent + TinyCUALoop. |
| `orchestration/router_node.md` | merge/delete | `loops/route_map.md` | RouterNode replaced by DecisionNode-owned RouteMap. |
| `orchestration/worker.md` | merge/delete | `loops/worker_concept.md` | Worker graph becomes `TinyCUAWorkerNode`; no worker QueryAnalyst. |
| `loops/overview.md` | update | `loops/overview.md` | New loop architecture overview. |
| `loops/react_agent.md` | merge/delete | `loops/base_loop.md` | SDK loop relationship and BaseLoop contract. |
| `loops/query_analyst_loop.md` | merge/delete | `loops/node.md` | Retry/output behavior moves into node retry policy. |
| `loops/information_digestion_loop.md` | merge/delete | `loops/node.md`, `tools/digester.md` | Mandatory digest behavior moves into node retry/validation. |
| `loops/task_analyzer_loop.md` | merge/delete | `loops/node.md` | Node validation/retry policy. |
| `loops/task_assessor_loop.md` | merge/delete | `loops/node.md` | Node validation/retry policy. |
| `loops/task_executor_loop.md` | merge/delete | `loops/node.md` | Node validation/retry policy. |
| `loops/result_review_loop.md` | merge/delete | `loops/node.md` | Node validation/retry policy. |
| `loops/primary_agent_loop.md` | merge/delete | `loops/node.md` | Response behavior moves to `TinyCUAResponseNode`. |
| `config/types.md` | merge/delete | `config/node_config.md` | Node config hierarchy and policies. |
| `config/agents.md` | merge/delete | `config/node_config.md`, `config/session_config.md` | Per-node config dataclasses and SessionConfig. |
| `state/agent_state.md` | rename/update | `models/agent_state.md` | AgentState remains result/lifecycle state; not generic input transport. |
| `state/session.md` | rename/update | `models/session.md` | Per-node/root session, propagation, dedupe, SDK messages. |
| `state/state_store.md` | rename/update | `models/state_store.md` | Persistence notes retained; datastore implementation out of roadmap scope. |
| `state/state_object.md` | rename/update | `models/state_object.md` | Base serialization for NodeInput/NodePayload. |
| `state/task.md` | rename/update | `models/task.md` | Task sharing notes retained. |
| `state/worker_result.md` | rename/update | `models/worker_result.md` | Worker result/restart under WorkerNode. |
| `state/reviewer_decision.md` | rename/update | `models/reviewer_decision.md` | Reviewer decisions retained. |
| `state/information.md` | rename/update | `models/information.md` | Query/digest states retained as AgentState outputs. |
| `state/execution_log.md` | rename/update | `models/execution_log.md` | Source node metadata. |
| `state/digested_information.md` | rename/update | `models/digested_information.md` | DigestedInformation retained. |
| `state/classification.md` | rename/update | `models/classification.md` | Top-level QueryAnalyst classification; remove worker QueryAnalyst labels as separate node. |
| `state/chat_record.md` | rename/update | `models/chat_record.md` | Source node metadata and dedupe IDs. |
| `constants/tools.md` | update | `constants/tools.md` | NodeToolPolicy and per-node tool scopes. |
| `constants/instructions.md` | update | `constants/instructions.md` | Hardcoded instruction + continuation constants. |
| `tools/digester.md` | keep/update | `tools/digester.md` | InformationDigester tools remain. |
| `tools/task.md` | keep/update | `tools/task.md` | Task tools remain. |
| `tools/todo.md` | keep/update | `tools/todo.md` | Todo tools remain. |
| `utility/compaction.md` | keep/update | `utility/compaction.md` | SessionConfig compaction. |
| `exceptions/loops.md` | merge/delete | `loops/tinycua_loop.md`, `loops/node.md` | TinyCUALoop/node error references. |

---

## Roadmap Draft Deliverable

After `docs/design/` is finalized, create:

```text
docs/roadmap/tinycua_architecture_implementation/
└── tinycua_architecture_implementation_main_issue_draft.md
```

The draft should follow `.github/ISSUE_TEMPLATE/roadmap.yml` conceptually. It should be scoped only to architecture implementation and exclude TUI, CLI, HITL UX, interrupt UX, datastore persistence, resume UX, and SDK modification.

Milestones should be sequential and PR-sized by default. Each milestone must include design docs covered, full/partial coverage, contract implemented, contract deferred, expected PR scope, and exit criteria. Avoid sub-issue drafts unless a milestone cannot reasonably be made PR-sized.

The draft directory is temporary review material. Before merge, convert the draft into a real GitHub issue and delete the draft directory unless the user decides to keep it.

---

## Implementation Phases

1. Rewrite planning docs.
2. Create new design docs.
3. Update retained docs.
4. Rename `state/` to `models/`.
5. Reconcile content and references.
6. Delete obsolete docs.
7. Create roadmap draft.
8. Verify docs-only diff.

---

## Technical Decisions

1. **Build around SDK, do not modify SDK**
   - **Reason**: Current SDK already passes `agent`, messages, tools, instruction overrides, and stream mode into loops.
   - **Alternatives Considered**: SDK changes — rejected for this design and roadmap scope.
2. **No Worker QueryAnalyst**
   - **Reason**: Worker can make deterministic checks first and call LLM only when dynamic worker routing is needed.
   - **Alternatives Considered**: Keep worker input-gate QueryAnalyst — rejected as unnecessary queue complexity.
3. **RouteMap remains DecisionNode-owned**
   - **Reason**: Keeps route inventory explicit without reintroducing RouterNode.
4. **NodeInput/NodePayload replaces YAML transport**
   - **Reason**: Avoids user injection and supports typed internal context.
5. **Suspension is queue-position based**
   - **Reason**: No extra state is needed; the suspended node remains queued behind prepended work.
6. **All node streams visible when stream=True**
   - **Reason**: Streaming should show the TinyCUA process, not only final response.
7. **Compaction strategy may own internal Agent**
   - **Reason**: Compaction is a separate summarization strategy selected by SessionConfig; it is not normal node execution inside TinyCUALoop.
8. **System prompt parts stay structured internally**
   - **Reason**: Multiple system messages are supported by current SDK canonical message handling, but structured prompt parts remain portable if a future provider needs single-message rendering.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Docs still imply old graph concepts as target architecture | Medium | High | Reconcile with stale-term search and migration table. |
| Roadmap milestones are too large | Medium | Medium | Require PR-sized milestones in draft. |
| SDK contract is accidentally misrepresented | Low | High | Explicitly document current Agent.run/BaseLoop.run inputs. |
| Context propagation becomes ambiguous | Medium | High | Separate chat_history, session_context, NodeInput, and PropagationRule docs. |
| Roadmap draft becomes permanent accidentally | Low | Low | Document it as temporary review material to convert/delete before merge. |

---

## References

- Spec: `./spec.md`
- SDK Agent: `src/tinycua-sdk/tinycua_sdk/agent/agent.py`
- SDK BaseLoop: `src/tinycua-sdk/tinycua_sdk/agent/loop.py`
- Roadmap template: `.github/ISSUE_TEMPLATE/roadmap.yml`
