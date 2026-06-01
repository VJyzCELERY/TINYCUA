# AgentGraph System Overview

> **File:** `docs/design/orchestration/overview.md`
> **Package:** `tinycua.orchestration`
> **Last Updated:** 2026-06-01
> **Status:** Draft — primary source of truth for TinyCUA runtime structure

---

## Role

TinyCUA runs as an **AgentGraph system**: a graph-level controller routes work across
AgentNodes, while each persistent AgentNode couples one SDK `Agent` with one `Session`,
and each SDK agent delegates execution policy to an agent-specific loop.

This document is the source of truth for the AgentGraph runtime:

1. **AgentGraph / Orchestrator** — top-level routing and graph execution.
2. **AgentNode** — outer wrapper: builds SDK Agent, calls `agent.run()`, yields events.
3. **AgentLoop** — inner loop: low-level streaming policy inside `agent.run(...)`.
4. **RouterNode / DecisionNode / Gates / Hooks** — graph-level routing and transforms.

---

## Naming Decision: AgentNode, not AgentNode

The previous docs used `AgentNode` for the node-level wrapper. To avoid confusion
with the `Session` state object, the preferred term is now **AgentNode**.

| Old term | New term | Why |
|----------|----------|-----|
| `BaseAgentOrchestrator` | `BaseAgentNode` | The class couples an agent with a session; it does not orchestrate graph flow |
| `BaseAgentNode` | `BaseAgentNode` | Avoids ambiguity with `Session` state object |
| AgentNode / AgentNode | AgentNode | Each internal agent is a node in the graph |
| `agent_node/` docs module | `agent_nodes/` in future | Current files may remain under `agent_node/` temporarily, but terminology should say AgentNode |

Use **AgentNode** for new design text. Existing file paths may remain
`agent_node/` until implementation/renaming happens.

---

## Layer Model

```text
AgentGraph / Orchestrator
  ├─ owns graph topology and decision routing
  ├─ owns input/output gates and graph hooks
  ├─ creates/links AgentNodes
  ├─ forwards YAML-front-matter state strings between nodes
  └─ persists/resumes the root Session tree

AgentNode
  ├─ outer loop: AgentNode.run(query: str)
  ├─ owns no duplicate config/state outside Session
  ├─ couples exactly one Session with one SDK Agent definition (unless stateless/transient process node)
  ├─ calls agent.run(query=..., messages=session.session_context)
  └─ yields inner-loop-produced stream/final events

AgentLoop
  ├─ inner loop: extends tinycua_sdk.agent.loop.BaseLoop
  ├─ passed as loop= parameter to tinycua_sdk.Agent(...)
  ├─ handles LLM retry and required tool enforcement
  ├─ formats final AgentState subclass output
  └─ writes session.agent_state

RouterNode / DecisionNode / Gates / Hooks
  ├─ sit at graph boundaries or graph edges
  ├─ preprocess, route, transform, or validate graph input/output
  └─ do not replace AgentLoop output enforcement
```

---

## Responsibilities

| Layer | Owns | Does NOT Own |
|-------|------|--------------|
| `AgentGraph` / Orchestrator | Routing, branching, node lifecycle, graph-level cancellation/resume, parent/child session tree | Required tool retry, node-local config duplication |
| `AgentNode` | Session↔Agent coupling, per-call SDK Agent construction, event passthrough, config override into session | Graph topology, decision routing, retry/output formatting, separate `self.state`/`self.config` |
| `AgentLoop` | Streaming policy, LLM retry, required tool enforcement, output formatting, writing `session.agent_state` | Creating graph nodes, owning persistent session tree |
| `RouterNode` / `DecisionNode` | Deterministic graph routing | Persistent session ownership, SDK Agent calls |
| `InputGate` / `OutputGate` | Graph boundary policy, input/output transformation, routing metadata | Node-local execution policy |
| `Session` | `AgentState`, `AgentConfigBase`, chat history, session context, task reference, child sessions | SDK runtime execution |

---

## Node Types

| Node Type | Has Session? | Can call SDK `Agent.run()`? | Purpose |
|-----------|--------------|------------------------------|---------|
| `AgentNode` | Yes | Yes | Standard internal agent node. Couples one SDK `Agent` with one `Session`. |
| `AgentGraph` / `Subgraph` | Yes (root Session) | Yes (via nodes) | Composite node containing its own graph; can be used as a node in a parent graph. |
| `ProcessNode` | No | Optional | Stateless processing step. |
| `RouterNode` | No | No | Exact-match string routing through `dict[str, Any]`; requires `default`. |
| `DecisionNode` | No by default | Usually no | Routes based on graph state, node results, predicates, or policy. |
| `InputGate` | Depends on target | Depends on target | Forces all graph input through a designated node/subgraph before routing. |
| `OutputGate` | Depends on target | Depends on target | Normalizes, validates, or transforms graph output before returning to caller. |

See [router_node.md](router_node.md) for the deterministic RouterNode contract.

---

## Composite Pattern

`AgentGraph` IS-A `Node`. A graph can contain another graph as a subgraph node:

```text
TinyCUA RootAgentGraph
 ├── InputGate(QueryAnalystNode)
 ├── RouterNode
 ├── PrimaryAgentNode
 └── TinyCUAWorkerGraph
      ├── InputGate(QueryAnalystNode)
      ├── TaskAnalyzerNode
      ├── TaskAssessorNode
      ├── TaskExecutorNode
      └── ResultReviewerNode
```

Subgraph boundaries are regular graph boundaries: they can have their own gates,
hooks, propagation rules, and session trees. A subgraph's output is consumed from its
root `session.agent_state` or through an explicit OutputGate.

---

## InputGate

An `InputGate` is a graph boundary node that always receives external or subgraph input
before that input reaches currently active nodes.

```text
external user query
  → InputGate(target=QueryAnalystNode)
      → gate output: QueryAnalystState YAML front-matter
      → RouterNode(state.classification)
```

InputGate target options:

| Target | Meaning |
|--------|---------|
| Single `AgentNode` | Run one node first for every graph input. |
| Set of nodes | Run multiple gate nodes and combine outputs. |
| Subgraph | Run a complete preliminary graph before entering the main graph. |

TinyCUA's root input gate uses `QueryAnalyst` with:

```text
TINYCUA_INPUT_GATE_CLASSIFICATION = ["passthrough", "worker"]
```

TinyCUAWorker's input gate uses the same QueryAnalyst implementation with different
labels:

```text
TINYCUA_WORKER_INPUT_GATE_CLASSIFICATION = [
  "task_recreation", "task_reanalysis", "proceed_execution"
]
```

The InputGate does not perform retry or output formatting itself. The wrapped
QueryAnalystNode uses `QueryAnalystLoop`, and that loop writes `QueryAnalystState` to
`query_analyst.session.agent_state`.

---

## OutputGate

An `OutputGate` is an optional graph boundary node that normalizes graph output before
returning it to the external caller. TinyCUA's default output direction is
`PrimaryAgentNode` so externally visible answers share a consistent final-response
shape.

Potential responsibilities:

- validate final response/citation shape
- redact internal graph metadata
- attach run/session identifiers
- convert final node output into an API response envelope

---

## AgentNode Input Contract: `run(query: str)`

Every AgentNode accepts a plain `str` query as its universal `run()` parameter.

```text
AgentNode.run(query: str) -> AsyncIterator[dict]
```

The graph always passes a single string. Structured data is embedded as YAML
front-matter produced by `AgentState.to_yaml()` and reconstructed by
`AgentState.from_string(query)`.

### YAML Front-Matter Pattern

```text
---
type: query_analyst
status: terminated
failure: 0
classification: worker
confidence: 0.91
context: |
  Relevant context analysis...
query: "Implement the worker graph"
---

<plain query tail, if any>
```

Parsing rule:

```text
parsed_state = AgentState.from_string(query)
if parsed_state is None:
    # plain string input
else:
    # parsed_state is the correct AgentState subclass, selected by `type`
```

If a string does not have front-matter, it is treated as plain text.

### Agents Following This Rule

| AgentNode | `run(query: str)` behavior |
|-----------|---------------------------|
| `QueryAnalyst` | Classifies + enriches directly; emits `QueryAnalystState` |
| `InformationDigester` | Parses `QueryAnalystState`; emits `InformationDigesterState` |
| `TaskAnalyzer` | Parses worker/input states; may receive TaskInit depending on classification |
| `TaskAssessor` | Parses `TaskAnalyzerState`; emits `TaskAssessorState` |
| `TaskExecutor` | Parses optional state, otherwise uses task tools; emits `TaskExecutorState` |
| `ResultReviewer` | Parses `TaskExecutorState`; emits `ResultReviewerState` or stays active |
| `PrimaryAgent` | Parses `QueryAnalystState`; appends CEQ context as assistant; emits `PrimaryAgentState` |

---

## Flexible Routing Philosophy

Because every AgentNode accepts a plain string and structured state is self-describing,
the graph can route any query to any node at any time.

```text
User: "This plan is wrong, re-plan subtask T-0.1"
  → InputGate(QueryAnalystNode)
  → classification = "passthrough"
  → current active node = TaskExecutorNode
  → graph routes user query to TaskExecutorNode
  → TaskExecutor writes TaskExecutorState(status=blocked)
  → ResultReviewer parses TaskExecutorState
  → decision = "replan"
  → Worker routes TaskAssessor → TaskAnalyzer
```

No graph edge needs a type-specific Python parameter. The receiver owns parsing.

---

## Propagation Rule

1. `AgentNode` owns a `Session`; termination/propagation follows
   `Session.terminate_child(...)`.
2. `AgentGraph` owns a root/subgraph session. Adjacent nodes are linked to that graph
   session.
3. `ProcessNode`, `RouterNode`, gates, and hooks do not automatically create sessions.
4. Transient AgentNodes can be used as gate/subgraph nodes when output is consumed
   inline.
5. Graph routing consumes `session.agent_state`; it should not parse raw SDK stream
   events.

---

## Task Inheritance Rule

By default, child sessions do **not** inherit their parent's `Task`. A Task is only
shared when the graph explicitly assigns it to a child session.

```text
AgentGraph (task: T-root)
  └─ Node1 (session.task = T-root)   ← explicit shared reference
       └─ Node2 (session.task = None) ← default: no inheritance
```

Task replacement propagation is controlled by `Session.share_parent_task`. See
[Session task sharing](../state/session.md#task-sharing-and-propagation).

---

## AgentLoop Execution Contract

Every AgentLoop owns behavior that should not live in node wrappers:

1. stream / continue the LLM as part of SDK execution
2. inspect tool calls internally when needed
3. retry missing required tool calls or invalid structured output
4. append first-response assistant text according to agent policy
5. format one final AgentState subclass
6. write `session.agent_state`

The graph consumes `session.agent_state`, not raw loop internals.

---

## Module Layout

```text
tinycua/
├── orchestration/      # AgentGraph, RouterNode, TinyCUA, TinyCUAWorker
├── agent_nodes/        # future name for node wrappers (currently docs/agent_node)
├── loops/              # AgentLoop implementations
├── state/              # StateObject, AgentState subclasses, Session, Task
├── tools/              # Task tools, ClassificationTool, TodoList, digester tools
├── constants/          # Tool + instruction constants
└── config/             # Agent config dataclasses
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Rename to AgentNode | Prefer `AgentNode` over `AgentNode` | Avoid confusion with `Session` state object |
| TinyCUA is AgentGraph | Graph-level runtime, not AgentNode | Keeps routing separate from node execution |
| Node interface | `run(query: str)` | Universal routing interface |
| Structured output | AgentState YAML front-matter | Self-describing, reconstructable, string-compatible |
| Graph consumes state | `session.agent_state`, not `last_result` | Agent-specific output lives directly on state subclasses |
| RouterNode | Exact match + default | Deterministic routing when LLM classification is unnecessary |
| Flexible routing | Any node reachable through passthrough + state parsing | Enables interruption, replan, steering |
| Task sharing explicit | Task assignment + `share_parent_task` | Prevents accidental cross-worker propagation |
| Loop owns retry/output | AgentLoop writes AgentState subclass | Keeps AgentNode thin and avoids event probing |

---

## See also

Next : [`TinyCUA AgentGraph`](tinycua.md)

## Related

- [RouterNode](router_node.md)
- [TinyCUAWorker AgentGraph](worker.md)
- [AgentState serialization](../state/agent_state.md)
- [Session task sharing](../state/session.md#task-sharing-and-propagation)
- [Base AgentNode (currently under agent_node/base.md)](../agent_node/base.md)
