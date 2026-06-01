# PrimaryAgentLoop

> **File:** `docs/design/loops/primary_agent_loop.md`
> **Last Updated:** 2026-06-01

---

## Role

Formats the final user-facing response and citations, appends the assistant output,
and writes `PrimaryAgentState` to `session.agent_state`.

```text
session.agent_state = PrimaryAgentState(
  type="primary_agent",
  status="terminated",
  final_response=response_text,
  citations=[...],
)
```

---

## Related

- [PrimaryAgent AgentNode](../agent_sessions/primary_agent.md)
- [PrimaryAgentState](../state/information.md#primaryagentstate)
