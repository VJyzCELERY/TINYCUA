# TinyCUA AgentGraph

> **File:** `docs/design/orchestration/tinycua.md`
> **Package:** `tinycua.orchestration.tinycua`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`TinyCUA` is the top-level **AgentGraph** and the single external entry point. It owns
cross-node result flow.

It is not an AgentNode. Internal agents such as `QueryAnalyst`, `TinyCUAWorker`, and
`PrimaryAgent` are nodes/subgraphs under the top-level graph.

All external user queries route through the graph's **InputGate**, whose target is a
`QueryAnalystNode` configured with `TINYCUA_INPUT_GATE_CLASSIFICATION`:

```text
TINYCUA_INPUT_GATE_CLASSIFICATION = ["passthrough", "worker"]
```

The QueryAnalyst output is a `QueryAnalystState` stored on
`query_analyst.session.agent_state` and serializable as YAML front-matter.

---

## AgentGraph Class

```text
TinyCUA  ← top-level AgentGraph, implements composite Node interface

__init__(config: TinyCUAConfig | None, session: Session | None) -> None
  · create or attach root session
  · create internal AgentNodes / subgraphs
  · configure root QueryAnalyst with TINYCUA_INPUT_GATE_CLASSIFICATION

run(user_query: str) -> AsyncIterator[dict]
  · append user query to root session via session.append_user(user_query)
  · InputGate: run QueryAnalyst, consume events, read query_analyst.session.agent_state
  · route on QueryAnalystState.classification:
      passthrough → _route_passthrough(query_analyst_state)
      worker → _route_worker(query_analyst_state)
  · persist root session after graph run
```

No top-level `uncertain` route exists. If QueryAnalyst cannot decide, it stays active
or defaults to passthrough according to HITL policy.

---

## Routing Model

```text
User Query
  → InputGate(QueryAnalystNode)
      output: QueryAnalystState(type="query_analyst", classification="passthrough"|"worker", context, query)
      ├── passthrough
      │     ├── no active worker/reviewer/executor → PrimaryAgentNode
      │     └── active node exists                → current active AgentNode
      │
      └── worker
            → TinyCUAWorkerGraph
```

Routing consumes `session.agent_state` objects, not `last_result` dictionaries and not
raw SDK stream events.

---

## InputGate

`QueryAnalyst` is the TinyCUA InputGate target. Every external user query is converted
into a `QueryAnalystState` before graph routing.

```text
user_query
  → InputGate(target=QueryAnalystNode)
  → QueryAnalystState YAML front-matter
  → RouterNode({"passthrough": ..., "worker": ..., "default": ...})
```

The root InputGate can decide:

1. `passthrough` to `PrimaryAgentNode`
2. `passthrough` to the current active AgentNode (TaskExecutor, ResultReviewer, etc.)
3. `worker` to `TinyCUAWorkerGraph`

`uncertain` is intentionally removed. Human-in-the-loop is represented by an active
node ending with an open question and not terminating; the next user query routes back
through QueryAnalyst and then passthrough to that active node.

---

## Passthrough Routing

```text
_route_passthrough(qa_state: QueryAnalystState):
  · active = root_session.get_active_session()
  · if active is root_session or no active worker node exists:
      → PrimaryAgentNode.run(qa_state.to_yaml() + "\n" + qa_state.query)
  · else:
      → active_node.run(qa_state.to_yaml() + "\n" + qa_state.query)
```

If passthrough targets `PrimaryAgentNode`, PrimaryAgent parses `QueryAnalystState`,
appends `qa_state.context` to the parent session context as an assistant message, and
runs `agent.run(query=qa_state.query, messages=parent.session_context)`.

The original query is **not** re-added to session history because `TinyCUA.run()`
already called `session.append_user(user_query)`.

---

## Worker Routing

```text
_route_worker(qa_state: QueryAnalystState):
  · create/activate TinyCUAWorkerGraph
  · explicitly share parent task if needed:
      worker.session.task = root_session.task
      worker.session.share_parent_task = True
  · pass QueryAnalystState as YAML front-matter:
      worker.run(qa_state.to_yaml() + "\n" + qa_state.query)
```

`TinyCUAWorker` owns worker-specific input gate classification, task creation,
decomposition, execution, review, retry, and replan. See [worker.md](worker.md).

---

## Flexible Routing Philosophy

TinyCUA's graph is designed so that **any node is reachable from any point**, not just
through a rigid linear pipeline. The InputGate always sees external queries first, but
the graph can route passthrough to the currently active node.

```text
# Replan example: user interrupts during task execution
User: "This plan is wrong, I need to re-plan subtask T-0.1"
  → InputGate(QueryAnalystNode)
  → classification = "passthrough"
  → current active = TaskExecutorNode
  → graph routes user query to TaskExecutorNode
  → TaskExecutor writes TaskExecutorState(status=blocked)
  → ResultReviewer receives TaskExecutorState
  → ResultReviewer decision = "replan"
  → TinyCUAWorker routes TaskAssessor → TaskAnalyzer
```

Structured payloads cross graph edges only as strings with AgentState YAML
front-matter. The receiver owns parsing.

---

## Session Tree

```text
TinyCUA root Session
 ├── QueryAnalyst            [transient input gate]
 ├── TinyCUAWorker           [AgentGraph subgraph]
 │    ├── QueryAnalyst       [transient worker input gate]
 │    ├── TaskAnalyzer
 │    ├── TaskAssessor
 │    ├── TaskExecutor
 │    └── ResultReviewer
 └── PrimaryAgent            [inherits parent session directly when used as passthrough]
```

Each persistent node's config and state live on that node's `session.agent_state`.
Transient nodes keep their own session while running but do not become durable tree
children.

---

## OutputGate Direction

TinyCUA can optionally add an OutputGate around graph exits. The default direction is
to make `PrimaryAgentNode` the output gate target so all externally visible answers
share a single final-response shape.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| TinyCUA is AgentGraph | Plain graph-level runtime, not `BaseAgentNode` | Keeps graph routing separate from node wrappers |
| Root input gate | `QueryAnalystNode` configured with `["passthrough", "worker"]` | Central routing decision without special uncertainty label |
| No uncertainty label | Indecision = active node/open question or passthrough fallback | Same HITL pattern as ResultReviewer; no extra route needed |
| Worker is subgraph | `TinyCUAWorkerGraph` handles task lifecycle | Encapsulates worker-specific routing and review loop |
| Node result routing | Read `session.agent_state` AgentState subclasses | Graph consumes typed state, not raw events or last_result dicts |
| Universal `run(query: str)` | Every AgentNode receives a plain string | Enables flexible routing |
| Structured pass-through | AgentState YAML front-matter | Self-describing and reconstructable via `AgentState.from_string()` |
| Passthrough to PrimaryAgent | Append QA context as assistant; run original query | Preserves QueryAnalyst context without duplicating user input |
| Task sharing explicit | Worker receives parent task by assignment | Prevents accidental task coupling; propagation controlled by `share_parent_task` |

---

## See also

Prev : [`AgentGraph System Overview`](overview.md) | Next : [`RouterNode`](router_node.md)

## Related

- [RouterNode](router_node.md)
- [TinyCUAWorker AgentGraph](worker.md)
- [QueryAnalyst input gate](../agent_sessions/query_analyst.md)
- [PrimaryAgent passthrough target](../agent_sessions/primary_agent.md)
- [Session is graph state](../state/session.md)
- [AgentState YAML front-matter](../state/agent_state.md)
