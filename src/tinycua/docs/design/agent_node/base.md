# BaseAgentNode

> **File:** `docs/design/agent_node/base.md`
> **Package:** `tinycua.agent_nodes.base`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`BaseAgentNode` is the node-level wrapper that couples a TinyCUA `Session` with an SDK
`Agent`.

It is intentionally not an orchestrator. Graph-level orchestration belongs to
`tinycua.orchestration`.

The `Session` is the source of truth for:

- `session.agent_state` (AgentState subclass output + lifecycle)
- `session.agent_state.agent_config`
- `session.session_context`
- `session.chat_history`
- `session.task`
- `session.todo_list`

The AgentNode's job is to connect those session-owned objects to an SDK `Agent` and
allow saving state for the stateless SDK `Agent` object, enabling the AgentNode to
couple a `Session` and `Task` tree with an SDK `Agent` that can be orchestrated by
the AgentGraph.

---

## Responsibility Split

| Layer | Owns | Does NOT Own |
|-------|------|--------------|
| `AgentGraph` | Routing, graph topology, node lifecycle, cross-node state flow | Required tool retry, node-local output formatting |
| `AgentNode` | Session wiring, per-call SDK Agent construction, event passthrough | Routing, duplicated state/config, tool-call probing |
| Agent-specific loop | LLM retry, required tool enforcement, final AgentState formatting | Graph routing, session tree creation |
| `Session` | AgentState, AgentConfigBase, session context, chat history, task reference | SDK runtime execution |
| SDK `Agent` | LLM/tool streaming runtime | TinyCUA persistence/routing policy |

---

## Class Contract

```text
BaseAgentNode(ABC)  ← thin Session ↔ SDK Agent connector

session: Session  — source of truth for state, config, context, history

__init__(config: AgentConfigBase | None, session: Session | None) -> None
   · if no session → create new Session with agent_state.agent_config = config
   · if session exists + config → overwrite session.agent_state.agent_config
   · stores session; does NOT retain separate self.config copy
   · build and cache the base instruction once: self._instruction = self._build_instruction()

@property config -> AgentConfigBase
  · convenience accessor → self.session.agent_state.agent_config

@abstractmethod
run(query: str) -> AsyncIterator[dict]
  · build a fresh tinycua_sdk.Agent per call with loop=SpecificAgentLoop(session=self.session)
  · call agent.run(query=query, messages=self.session.session_context, stream=True)
  · yield all stream events (loop owns retry/output)
```

---

## Universal Input Contract

Every AgentNode uses:

```text
run(query: str) -> AsyncIterator[dict]
```

The graph passes structured data between nodes by prepending AgentState YAML
front-matter to the query string. This keeps routing information self-describing
while maintaining the single-string interface.

`AgentState.from_string(query)` separates the front-matter block from the trailing
content:

```text
parsed = AgentState.from_string(query)   # → AgentState subclass or None
remaining = AgentState.strip_string(query)  # → content after front-matter, if any
```

If no front-matter is present, `parsed` is `None` and `remaining` is the entire
string.

The graph never passes dicts or typed Python objects between nodes.

### Front-Matter Rule

YAML front-matter is a **graph-level routing and classification helper only**. It is
never consumed as structured data by the agent itself. The agent always receives a
plain string query — the raw YAML block is stripped before the query reaches the SDK
`Agent`.

Each AgentNode documents which AgentState types it **natively supports** (e.g.,
TaskExecutor handles `ResultReviewerState`, PrimaryAgent handles `QueryAnalystState`).
When a supported state is received, the node extracts relevant fields and may use
them to adapt behavior. When an **unsupported** state is received, the node treats
the entire input as a plain query — no structured extraction happens.

### Unsupported State Handling

When a node receives an AgentState type it does not support (e.g., TaskExecutor
receives `TaskAssessorState`), it falls back to rendering the state's fields as
descriptive markdown text. The front-matter is discarded; only the rendered
markdown + trailing content reaches the agent:

```text
run(query):
  parsed = AgentState.from_string(query)
  remaining = AgentState.strip_string(query)

  if parsed is None:
      agent_query = query                         # plain string, pass through
  elif isinstance(parsed, SUPPORTED_STATE_TYPES):
      agent_query = _build_query(parsed, remaining)  # structured extraction
  else:
      agent_query = _fallback_query(parsed, remaining)  # render as markdown text
```

The fallback rendering converts the state's typed fields into human-readable
prose or bullet points (e.g., `TaskAssessorState(verdict="analyze", analysis="...")`
becomes `"Assessment verdict: analyze\n\nAnalysis: ..."`). No raw YAML, no
structured field names — the agent sees only plain conversational text.

This ensures that:
- Front-matter remains a graph-internal routing mechanism
- No raw YAML leaks into the agent's conversational context
- Unsupported states degrade gracefully instead of being silently ignored or
  causing parse errors

---

## Per-Call Agent Construction

```text
async run(self, query: str) -> AsyncIterator[dict]:
  config = self.session.agent_state.agent_config
  agent_query = self._build_query(query)

  agent = tinycua_sdk.Agent(
      name=config.name,
      instructions=self._instruction,   # built once in __init__, cached for provider prompt caching
      llm_model=config.model,
      tools=[*BASE_TOOLS, *config.extra_tools],
      loop=SpecificAgentLoop(session=self.session),
  )

  async for event in agent.run(query=agent_query,
                               messages=self.session.session_context,
                               stream=True):
      yield event
```

The final event/result is produced by the inner loop. The outer AgentNode does not
inspect the stream to find tool calls, parse markdown/JSON, or run follow-up retries.

---

## Inner Loop Output Contract

```text
agent.run(...)
  → SDK streams normal events
  → inner loop enforces required tool calls / retry policy
  → inner loop appends assistant messages to session when appropriate
  → inner loop writes an AgentState subclass to session.agent_state
  → inner loop emits final result event
```

The AgentGraph reads `node.session.agent_state` after the node run.

---

## AgentGraph Integration

```text
node = QueryAnalyst(session=child_session, config=override)
async for event in node.run(query=user_query): yield event

state = node.session.agent_state  # QueryAnalystState
next_node = graph.route(state.classification)
next_node.run(query=state.to_yaml() + "\n" + state.query)
```

Routing decisions belong to the graph, not the AgentNode.

---

## Instruction Prompt Caching

Each AgentNode builds its complete instruction string once in `__init__` and caches it
as `self._instruction`. The cached instruction is reused across every `run()` call for
the lifetime of the node. This enables provider-level prompt caching (e.g., Anthropic
prefix caching, OpenAI prompt caching) to hit on the system message across consecutive
LLM calls.

Instruction strings should be kept **minimally dynamic**. Dynamic context that changes
between calls (task-tree snapshot, session metadata, project files) should be passed in
per-call messages — not by rebuilding the instruction string. This keeps the
instruction prefix stable so the provider can reuse the cached computation.

When a node transitions across a major lifecycle boundary (e.g., Worker recreation), a
new AgentNode instance is created, which naturally builds a fresh instruction. Within a
single node's lifetime, the instruction is immutable.

---

## Interrupt / Steering Consideration

AgentNodes and loops should not assume a stream is always uninterrupted. Future
interrupt support may live in the SDK stream protocol, the loop layer, the AgentGraph
layer, or a combination.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Rename node wrapper | `BaseAgentNode` | Avoids confusion with `Session` |
| Session owns config/state | `session.agent_state.agent_config` + `session.agent_state` | No duplicated node state |
| Cached instruction | Built once in `__init__` → `self._instruction` | Enables provider-level prompt caching; avoids per-call string rebuild |
| Thin AgentNode | Build Agent, pass context, yield events | Keeps wrapper simple |
| Loop-owned retry | Agent-specific loops retry inside `agent.run()` | No external retry wrapper |
| Loop-owned output formatting | Loop writes AgentState subclass | AgentNode does not probe raw events |
| Universal input | `run(query: str)` | Enables flexible routing |
| Graph owns routing | Graph consumes `session.agent_state` | Keeps routing separate from node execution |

---

## See also

Prev : [Continuation State Store](../state/state_store.md) | Next : [AgentNode Factory](factory.md)

## Related

- [AgentGraph system overview](../orchestration/overview.md)
- [Session owns AgentState and config](../state/session.md)
- [AgentState serialization](../state/agent_state.md)
- [Loop responsibility split](../loops/overview.md)
