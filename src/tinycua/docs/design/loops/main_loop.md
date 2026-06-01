# MainLoop

> **File:** `docs/design/loops/main_loop.md`
> **Last Updated:** 2026-06-01

---

## Role

`MainLoop` is the graph-level loop used when TinyCUA composes an SDK `Agent` for
delegating to AgentNodes. The current design is moving routing responsibility into
explicit AgentGraph/RouterNode/TinyCUAWorker structures, so MainLoop should be treated
as an integration adapter rather than the source of truth for graph policy.

Source of truth for routing:

- [TinyCUA AgentGraph](../orchestration/tinycua.md)
- [TinyCUAWorker AgentGraph](../orchestration/worker.md)
- [RouterNode](../orchestration/router_node.md)

---

## Contract

```text
MainLoop(session: Session, agent_nodes: dict[str, BaseAgentNode])
```

If used, it delegates to AgentNodes through tools/calls and then reads each node's
`session.agent_state` output. It must not rely on `last_result` dictionaries,
`active_agent`, `uncertain`, or `escalate_user`.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Adapter, not source of truth | Graph docs own routing policy | Avoid duplicate graph definitions |
| AgentNode terminology | `agent_nodes` | Avoid confusion with Session |
| State output | consume `session.agent_state` | New AgentState subclass model |
| No uncertain/escalate routes | use active/open-question behavior | Consistent with QueryAnalyst and ResultReviewer |

---

## Related

- [AgentGraph overview](../orchestration/overview.md)
- [TinyCUA](../orchestration/tinycua.md)
- [TinyCUAWorker](../orchestration/worker.md)
- [AgentNode call tools](../tools/agent_calls.md)
