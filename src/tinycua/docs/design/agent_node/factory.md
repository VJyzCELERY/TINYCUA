# AgentNode Factory

> **File:** `docs/design/agent_node/factory.md`
> **Package:** `tinycua.agent_nodes.factory`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`create_agent_node()` and `create_all_agent_nodes()` construct typed AgentNodes from
config dataclasses. Each AgentNode stores config by writing it into
`session.agent_state.agent_config`. No SDK `Agent` is created at factory time — that
happens inside each AgentNode's `run(query: str)` method.

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
```

---

## Internal Flow

```text
create_agent_node(AgentKind.QUERY_ANALYST, config)
  → Look up or use QueryAnalystConfig
  → Construct QueryAnalyst(config)
  → session.agent_state.agent_config = config
  → Return AgentNode instance
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Factory returns AgentNode, not Agent | `BaseAgentNode` subclass | AgentGraph interacts through `run(query: str)` |
| Config lives in Session | Factory writes config to `session.agent_state.agent_config` | Avoids duplicate source of truth |
| No Agent in factory | SDK Agent built per-call | Loop receives current session each invocation |
| Excludes AgentGraph | Internal AgentNodes only | TinyCUA/TinyCUAWorker graphs are composers, created separately |

---

## See also

Prev : [`BaseAgentNode`](base.md) | Next : [`QueryAnalyst` AgentNode](query_analyst.md)

## Related

- [BaseAgentNode](base.md)
- [AgentGraph system overview](../orchestration/overview.md)
- [AgentKind enum for lookup](../config/types.md)
- [Config dataclasses](../config/agents.md)
