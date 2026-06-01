# TinyCUA AgentGraph

> **File:** `docs/design/orchestration/tinycua.md`
> **Package:** `tinycua.orchestration.tinycua`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`TinyCUA` is the top-level **AgentGraph** and the single external entry point. It owns
the root execution queue and cross-node result flow.

It is not an AgentNode and it does not construct a top-level SDK `Agent` object. Its
job is deterministic graph orchestration: route input to AgentNodes/subgraphs, create
or activate nodes when needed, and persist the root session tree. Internal agents such
as `QueryAnalyst`, `TinyCUAWorker`, and `PrimaryAgent` are nodes/subgraphs under the
top-level graph.

External user queries normally route through the graph's **InputGate**, whose target is
a `QueryAnalystNode` configured with `TINYCUA_INPUT_GATE_CLASSIFICATION`:

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
  · seed or update the root graph queue
  · create internal AgentNodes / subgraphs lazily when they become queue[0]
  · configure root QueryAnalyst with TINYCUA_INPUT_GATE_CLASSIFICATION
  · do not create a top-level SDK Agent or AgentLoop

run(user_query: str) -> AsyncIterator[dict]
  · append user query to root session via session.append_user(user_query)
  · if active node requires direct continuation / steering passthrough:
      route user_query directly to active node without QueryAnalyst
  · otherwise InputGate: run QueryAnalyst, consume events, read query_analyst.session.agent_state
  · route on QueryAnalystState.classification:
      passthrough → _route_passthrough(query_analyst_state)
      worker → _route_worker(query_analyst_state)
  · persist root session after graph run
```

No top-level `uncertain` route exists. If QueryAnalyst cannot decide, it stays active
or defaults to passthrough according to HITL policy.

---

## Queue Shape

TinyCUA tracks the active node with its root queue. A common worker-capable shape is:

```text
[QueryAnalyst, InformationDigester, TinyCUAWorker]
```

Only index `0` is active. Queued future nodes do not create sessions until activated.
For example, `InformationDigester` may be present in the queue while its session does
not exist yet.

If the graph already has an active worker and a new external user query arrives on the
normal classification path, the input gate is temporarily prepended:

```text
Before input: [TinyCUAWorker]
During input: [QueryAnalyst, TinyCUAWorker]
```

TinyCUA knows the graph-level active node is `TinyCUAWorker`; it does not know or
inspect whether the worker's internal queue is currently at TaskExecutor,
ResultReviewer, or another child.

---

## Routing Model

```text
User Query
  → InputGate(QueryAnalystNode)
      output: QueryAnalystState(type="query_analyst", classification="passthrough"|"worker", context, query)
      ├── passthrough
      │     ├── no active worker/subgraph → PrimaryAgentNode(terminal)
      │     └── active worker exists      → existing TinyCUAWorkerGraph
      │
      └── worker
            ├── no active worker    → InformationDigester → TinyCUAWorkerGraph
            └── active worker exists → InformationDigester → existing TinyCUAWorkerGraph
```

Routing consumes `session.agent_state` objects, not `last_result` dictionaries and not
raw SDK stream events.

---

## InputGate

`QueryAnalyst` is the TinyCUA InputGate target for normal top-level routing. External
user queries are converted into a `QueryAnalystState` before graph routing unless the
current active node requires direct continuation / steering passthrough.

```text
user_query
  → InputGate(target=QueryAnalystNode)
  → QueryAnalystState YAML front-matter
  → RouterNode({"passthrough": ..., "worker": ..., "default": ...})
```

The root InputGate can decide:

1. `passthrough` to `PrimaryAgentNode` as a terminal node when no worker/subgraph is active
2. `passthrough` to the existing active `TinyCUAWorkerGraph` when a worker is active
3. `worker` to `InformationDigester → TinyCUAWorkerGraph` (new or existing worker)

`uncertain` is intentionally removed. Human-in-the-loop is represented by an active
node ending with an open question and not terminating; the next user query passes back
to that active node either by direct continuation or by QueryAnalyst passthrough.

---

## Passthrough Routing

```text
_route_passthrough(qa_state: QueryAnalystState):
  · active = root_queue.peek_after_input_gate()
  · if active is TinyCUAWorkerGraph:
      queue.replace_after_active([existing_worker.with_input(qa_state.to_yaml() + "\n" + qa_state.query)])
  · else:
      queue.replace_after_active([PrimaryAgentNode(terminal=True).with_input(qa_state.to_yaml() + "\n" + qa_state.query)])
```

If passthrough targets `PrimaryAgentNode`, PrimaryAgent parses `QueryAnalystState`,
appends `qa_state.context` to the parent session context as an assistant message, and
runs `agent.run(query=qa_state.query, messages=parent.session_context)`.

The original query is **not** re-added to session history because `TinyCUA.run()`
already called `session.append_user(user_query)`.

---

## Passthrough Reliability Considerations

Passthrough must be reliable because it carries steering, human-in-the-loop replies,
and continuation input back to the currently active agent.

### Running Active Agent Bypass

If the current active AgentNode has `session.agent_state.status == "running"`, TinyCUA
should treat the next external input as steering / continuation input for that active
agent. In that case, route directly to the active node and skip QueryAnalyst.

```text
if active.session.agent_state.status == "running":
    active.run(user_query)   # no QueryAnalyst classification
```

If the input is out of scope, the active agent is responsible for terminating itself
gracefully or handing control back through its normal output state. The graph should not
pre-judge steering intent by running another classifier first.

### Idle Active Agent and HITL Signals

An idle active agent may still be waiting for human input even if it did not terminate.
Design should allow an agent to emit a supplemental "HITL required" / "human next input
requested" signal without changing the core `AgentStatus` enum. When that signal is
present, the next user input should pass through to that agent instead of being treated
as a fresh top-level request.

This signal is not yet a finalized schema field; the design requirement is that
passthrough routing must have a reliable way to distinguish:

- idle because the agent is waiting for the human;
- idle because the agent has finished or should be terminated;
- idle because status was underspecified and needs monitoring.

### Internal Continuation Resolution

If an active agent is non-terminal but does not clearly request HITL, TinyCUA may use a
monitoring hook to resolve ambiguity before deciding whether the next input should
passthrough or start a new QueryAnalyst route. See [Base AgentNode](../agent_node/base.md#agentmonitor--monitoring-hook-consideration).

---

## Worker Routing

```text
_route_worker(qa_state: QueryAnalystState):
  · if an existing worker is queued/active, reuse it as an opaque graph node
  · otherwise schedule a new TinyCUAWorkerGraph
  · explicitly share parent task if needed:
      worker.session.task = root_session.task
      worker.session.share_parent_task = True
  · queue InformationDigester before the worker:
      [InformationDigester.with_input(qa_state.to_yaml() + "\n" + qa_state.query), worker]
```

`TinyCUAWorker` owns worker-specific input gate classification, task creation,
decomposition, execution, review, retry, and replan. See [worker.md](worker.md).

### Worker Restart Result

If an existing worker terminates with:

```text
TinyCUAWorkerState(restart_requested=True, handoff_query=<query>)
```

TinyCUA removes that worker from the root queue, creates a fresh worker, and schedules
the `handoff_query` against the new worker. TinyCUA does not inspect the terminated
worker's internal queue or child AgentNodes.

---

## Flexible Routing Philosophy

TinyCUA's graph is designed so that **any node is reachable from any point**, not just
through a rigid linear pipeline. The InputGate normally sees external queries first,
but direct continuation / steering may bypass it when the active node is already
running or clearly waiting for human input.

```text
# Replan example: user interrupts during task execution
User: "This plan is wrong, I need to re-plan subtask T-0.1"
  → InputGate(QueryAnalystNode)
  → classification = "passthrough"
  → current top-level active = TinyCUAWorkerGraph
  → TinyCUA routes passthrough to TinyCUAWorkerGraph
  → Worker internally decides whether the input goes to TaskExecutor, ResultReviewer, or replanning
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
| No top-level SDK Agent | TinyCUA routes to AgentNodes/subgraphs directly | Passthrough/fallback behavior belongs to `PrimaryAgentNode`, not a graph-level agent |
| Active node tracking | Root queue first item | TinyCUA always knows the active top-level node without inspecting nested worker state |
| Root input gate | `QueryAnalystNode` configured with `["passthrough", "worker"]` | Central routing decision without special uncertainty label |
| No uncertainty label | Indecision = active node/open question or passthrough fallback | Same HITL pattern as ResultReviewer; no extra route needed |
| Worker is subgraph | `TinyCUAWorkerGraph` handles task lifecycle | Encapsulates worker-specific routing and review loop |
| Node result routing | Read `session.agent_state` AgentState subclasses | Graph consumes typed state, not raw events or last_result dicts |
| Universal `run(query: str)` | Every AgentNode receives a plain string | Enables flexible routing |
| Structured pass-through | AgentState YAML front-matter | Self-describing and reconstructable via `AgentState.from_string()` |
| Passthrough to PrimaryAgent | Append QA context as assistant; run original query | Preserves QueryAnalyst context without duplicating user input |
| Passthrough reliability | Running/HITL active nodes receive direct continuation | Steering and human replies should not be reclassified as fresh tasks |
| Task sharing explicit | Worker receives parent task by assignment | Prevents accidental task coupling; propagation controlled by `share_parent_task` |

---

## See also

Prev : [`AgentGraph System Overview`](overview.md) | Next : [`RouterNode`](router_node.md)

## Related

- [RouterNode](router_node.md)
- [AgentGraph Queue System](graph_queue.md)
- [TinyCUAWorker AgentGraph](worker.md)
- [QueryAnalyst input gate](../agent_node/query_analyst.md)
- [PrimaryAgent passthrough target](../agent_node/primary_agent.md)
- [Session is graph state](../state/session.md)
- [AgentState YAML front-matter](../state/agent_state.md)
