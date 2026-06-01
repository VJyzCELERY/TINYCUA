# AgentNode-Call Tools

> **File:** `docs/design/tools/agent_calls.md`
> **Package:** `tinycua.tools.agent_calls`
> **Last Updated:** 2026-06-01

---

## Role

AgentNode-call tools are optional SDK `Tool` adapter objects that invoke an internal
AgentNode through its `run(query: str)` method.

They are an adapter pattern only, mainly useful for tests or legacy integration paths.
Explicit AgentGraph routing in
[`orchestration/tinycua.md`](../orchestration/tinycua.md) and
[`orchestration/worker.md`](../orchestration/worker.md) remains the source of truth.

---

## Contract

```text
call_query_analyst(agent_nodes: dict[AgentKind, BaseAgentNode]) → Tool
  execute(query: str) → str
    · node = agent_nodes[AgentKind.QUERY_ANALYST]
    · consume async for event in node.run(query=query)
    · return node.session.agent_state.to_yaml()
```

Tools return serialized `AgentState` YAML, not `last_result` dictionaries.

---

## Tool Table

| Tool | Target AgentNode | Returns |
|------|------------------|---------|
| `call_query_analyst(agent_nodes)` | `QueryAnalyst` | `QueryAnalystState.to_yaml()` |
| `call_information_digester(agent_nodes)` | `InformationDigester` | `InformationDigesterState.to_yaml()` |
| `call_task_analyzer(agent_nodes)` | `TaskAnalyzer` | `TaskAnalyzerState.to_yaml()` |
| `call_task_assessor(agent_nodes)` | `TaskAssessor` | `TaskAssessorState.to_yaml()` |
| `call_task_executor(agent_nodes)` | `TaskExecutor` | `TaskExecutorState.to_yaml()` |
| `call_result_reviewer(agent_nodes)` | `ResultReviewer` | `ResultReviewerState.to_yaml()` if terminal |
| `call_primary_agent(agent_nodes)` | `PrimaryAgent` | `PrimaryAgentState.to_yaml()` |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tools receive AgentNode | `node.run(query)` | Preserves session state, loop integrity, and node lifecycle |
| Return YAML state | `node.session.agent_state.to_yaml()` | Compatible with universal string routing |
| No raw SDK Agent bypass | Never call `agent.run()` directly | Keeps loop/session policy intact |
| Adapter only | Graph docs own routing | Avoids natural-language delegation becoming source of truth |

---

## Related

- [AgentNode factory](../agent_node/factory.md)
- [BaseAgentNode](../agent_node/base.md)
- [AgentState serialization](../state/agent_state.md)
