# InformationDigestionLoop

> **File:** `docs/design/loops/information_digestion_loop.md`
> **Last Updated:** 2026-06-01

---

## Role

Enforces at least one `digest_information` call, tracks retrieval iterations, and
writes `InformationDigesterState` to `session.agent_state`.

```text
session.agent_state = InformationDigesterState(
  type="information_digester",
  status="terminated",
  context_summary=...,
  key_points=[...],
  retrieval_iterations=N,
)
```

---

## Related

- [InformationDigester AgentNode](../agent_sessions/information_digester.md)
- [InformationDigesterState](../state/information.md#informationdigesterstate)
