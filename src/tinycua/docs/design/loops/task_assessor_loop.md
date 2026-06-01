# TaskAssessorLoop

> **File:** `docs/design/loops/task_assessor_loop.md`
> **Last Updated:** 2026-06-01

---

## Role

Enforces the assessor ClassificationTool (`analyze` / `stop`) and writes
`TaskAssessorState` to `session.agent_state`.

```text
if missing verdict after retries:
  verdict = "stop"

session.agent_state = TaskAssessorState(
  type="task_assessor",
  status="terminated",
  verdict=verdict,
  analysis=first_response_text,
)
```

---

## Related

- [TaskAssessor AgentNode](../agent_sessions/task_assessor.md)
- [TaskAssessorState](../state/information.md#taskassessorstate)
