# Design Document: TinyCUA Design Simplification — Documentation Reorganization

**Spec**: [./spec.md](./spec.md)
**Status**: In Progress
**Last Updated**: 2026-06-04

---

## Overview

This design reorganizes `src/tinycua/docs/design/` around a simplified TinyCUA runtime model that builds on, not around, the current `tinycua-sdk` contract. The target architecture is one SDK `Agent` configured with `TinyCUALoop`, where `TinyCUALoop` extends SDK `BaseLoop`, processes a sequential `NodeQueue`, and runs concrete TinyCUA-specific nodes. The design preserves useful existing graph/session behavior — propagation, task sharing, passthrough, retry, and streaming — while removing the target concepts of `AgentGraph`, `RouterNode`, `AgentNode`, worker QueryAnalyst, per-agent loops, and generic `PrimaryNode`.

This PR is documentation-only. It reorganizes design docs and creates a reviewable roadmap issue draft. It does not implement the runtime.

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

Conceptual execution:

```text
TinyCUALoop.run(agent, messages, tools, override_instructions, stream):
  1. Merge SDK messages into root session input context according to session policy.
  2. Ensure NodeQueue contains an entry node and terminal response path.
  3. While queue is not empty:
       node = queue.current
       node_session = node.ensure_session(...)
       input_messages = node.build_messages(root_session, node_input)
       instructions = node.build_instruction(override_instructions)
       scoped_tools = node.tool_policy.resolve(node_tools, outer_agent_tools=tools)
       result = call/stream agent._call_llm(input_messages, scoped_tools)
       validate/retry according to node retry policy
       record chat history and selected session context
       propagate according to PropagationRule
       node.on_complete(queue, result)
  4. Return final TinyCUAResponseNode string or stream events.
```

---

## NodeQueue

`NodeQueue` is the execution structure. `queue[0]` is the active node. Queue order determines execution order only; it does not automatically share context.

```text
NodeQueue
  · items: list[Node]
  · current → Node | None
  · advance() → None
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
```

RouteMap is not an independent orchestration layer. It is owned by concrete DecisionNode classes.

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

`TinyCUAResponseNode` is TinyCUA's final response/synthesis node. It derives from `ProcessNode`; it is not a generic `PrimaryNode` primitive.

It may be terminal and suspendable. If it needs more information, it can request `TinyCUAInformationDigesterNode` through queue suspension:

```text
ResponseNode session_context
  → NodeInput(messages=response_node.session_context, payloads=[InformationDigestRequest])
  → InformationDigesterNode(parent=ResponseNode)
  → digest result propagates back to ResponseNode
  → ResponseNode resumes final synthesis
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

A `Todo` is a small, isolated, linear, non-complex todo list stored per session. Every node can access its session's `Todo` to plan then execute in a structured manner. It is not a full task-planning or project-management system — just a simple ordered list the node can read, check off, and extend during execution.

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

1. Inherit the parent SDK Agent configuration where available, especially language model
   and provider configuration.
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
  · max_attempts
  · required_tool_calls
  · required_output_schema
  · validation_fn
  · retry_continuation_builder
  · on_retry_exhausted
```

The loop owns mechanics: call LLM, stream events, repeat attempts, and log retry continuations. The node owns policy: what is valid, how to retry, and how to handle exhaustion.

---

## AgentMonitor / NodeMonitor Consideration

The old AgentMonitor concept remains as an optional transient hook. It is not a durable queue node by default.

It may inspect an ambiguous active node and decide whether the node should continue internally, wait for user input, terminate, or escalate failure. Monitor-generated continuation messages are assistant-role internal messages.

---

## PropagationRule

`PropagationRule` preserves the old `Session.terminate_child(...)` behavior while making it explicit/configurable.

```text
PropagationRule
  · chat_history: none | parent | root
  · session_context: none | parent | root
  · session_context_mode: none | final | full | selected
  · token_usage: none | parent | root
  · failure: none | parent | root
  · dedupe: bool
```

Profiles:

| Profile | chat_history | session_context | token_usage | failure |
|---------|--------------|-----------------|-------------|---------|
| transient_legacy | parent/root | none | parent/root | parent/root |
| natural_termination_legacy | parent/root | final | parent/root | parent/root |
| mid_progress_legacy | parent/root | full | parent/root | parent/root |
| selected_internal_output | root | selected | root | root |

QueryAnalyst and InformationDigester may now propagate selected deduped context to root/parent while preserving full audit in chat history.

---

## Tool Scoping

Each node controls its tool exposure.

```text
NodeToolPolicy
  · node_tools
  · include_agent_tools: none | selected | all
  · allowed_agent_tool_names
  · denied_agent_tool_names
```

The outer SDK `Agent(tools=[...])` remains the source of caller-provided tools. TinyCUA chooses which of those tools each node can see.

| Node | Tool Scope |
|------|------------|
| TinyCUAQueryAnalystNode | classification + read-only task/context tools |
| TinyCUAInformationDigesterNode | enhanced retrieval + digest tools |
| TinyCUAWorkerNode | worker decision tools only |
| TinyCUATaskAnalyzerNode | task structure tools, optionally TaskInit/TaskCreate |
| TinyCUATaskExecutorNode | task tools + selected outer Agent tools |
| TinyCUAResultReviewerNode | review/decision tools |
| TinyCUAResponseNode | selected outer Agent tools + information-digestion request capability |

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
