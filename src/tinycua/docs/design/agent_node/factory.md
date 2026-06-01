# AgentNode Factory

> **File:** `docs/design/agent_node/factory.md`
> **Package:** `tinycua.agent_nodes.factory`
> **Last Updated:** 2026-06-02
> **Status:** Draft

---

## Role

`create_agent_node()` and `create_all_agent_nodes()` construct **fresh** typed
AgentNodes from config dataclasses. `load_agent_node()` reconstructs a typed
AgentNode wrapper around an existing `Session` loaded from persistence.

Each AgentNode stores config by writing it into `session.agent_state.agent_config`.
No SDK `Agent` is created at factory or hydration time — that happens inside each
AgentNode's `run(query: str)` method.

The docs path is `agent_node/` to match the AgentNode terminology.

---

## API

```text
create_agent_node(kind: AgentKind, config: AgentConfigBase | None) -> BaseAgentNode
  → Create one AgentNode from its config
  → If config is None, use the default config for the AgentKind

create_all_agent_nodes(config_overrides: dict[AgentKind, AgentConfigBase] | None) -> dict[AgentKind, BaseAgentNode]
  → Create all internal AgentNodes
  → config_overrides allows per-node customization

load_agent_node(session: Session) -> BaseAgentNode
  → Reconstruct one AgentNode wrapper from an existing Session
  → Infer AgentKind from session.agent_state.type
  → Preserve session.agent_state.agent_config as the config source of truth
  → Do not create a new Session
```

`load_agent_node()` is the persistence/hydration path. It should work for any
registered AgentNode subclass that extends `BaseAgentNode`; adding a new AgentNode
means registering its `AgentKind`, `AgentState.type`, default config, and node class.

Loading is intentionally **lazy**. Restoring a graph from persistence should not call
`load_agent_node()` for every saved child session up front. The graph keeps queue items
as lightweight descriptors (`AgentKind`, `session_id`, input, policy) and invokes
`load_agent_node(session)` only when that item becomes active, is explicitly resumed,
or must be inspected as a live runtime object.

---

## Internal Flow

```text
create_agent_node(AgentKind.QUERY_ANALYST, config)
  → Look up or use QueryAnalystConfig
  → Construct QueryAnalyst(config)
  → session.agent_state.agent_config = config
  → Return AgentNode instance

load_agent_node(existing_query_analyst_session)
  → Read existing_query_analyst_session.agent_state.type
  → Map type="query_analyst" to AgentKind.QUERY_ANALYST / QueryAnalyst
  → Validate session.agent_state.agent_config is compatible with QueryAnalystConfig
  → Construct QueryAnalyst(session=existing_query_analyst_session)
  → Return AgentNode instance attached to the existing Session
```

The loaded AgentNode is a runtime wrapper only. The persisted object is the
`Session` tree plus its `AgentState`, config, history, context, task references, and
graph queue metadata. SDK `Agent` instances and AgentNode wrapper objects are not
persisted.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Factory returns AgentNode, not Agent | `BaseAgentNode` subclass | AgentGraph interacts through `run(query: str)` |
| Config lives in Session | Factory writes config to `session.agent_state.agent_config` | Avoids duplicate source of truth |
| No Agent in factory | SDK Agent built per-call | Loop receives current session each invocation |
| Excludes AgentGraph | Internal AgentNodes only | TinyCUA/TinyCUAWorker graphs are composers, created separately |
| Separate create vs load | `create_agent_node()` is fresh; `load_agent_node()` hydrates | Avoids silently replacing existing sessions during resume |
| Registry-driven loading | `AgentState.type` / `AgentKind` maps to node class | Any `BaseAgentNode` subclass can be reconstructed consistently |
| Runtime wrapper only | Loaded AgentNode is rebuilt around persisted Session | Keeps persistence focused on durable state, not live Python objects |
| Lazy hydration | Call `load_agent_node()` on activation/resume, not bulk load | Prevents startup/resume from reconstructing inactive branches |

---

## See also

Prev : [`BaseAgentNode`](base.md) | Next : [`QueryAnalyst` AgentNode](query_analyst.md)

## Related

- [BaseAgentNode](base.md)
- [AgentGraph system overview](../orchestration/overview.md)
- [AgentKind enum for lookup](../config/types.md)
- [Config dataclasses](../config/agents.md)
