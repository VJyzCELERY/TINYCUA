# TaskAnalyzerLoop

> **File:** `docs/design/loops/task_analyzer_loop.md`
> **Last Updated:** 2026-06-01

---

## Role

Formats the final TaskAnalyzer response as a markdown analysis summary and writes
`TaskAnalyzerState` to `session.agent_state`. Task tree mutations happen through task
tools on `session.task`.

```text
session.agent_state = TaskAnalyzerState(
  type="task_analyzer",
  status="terminated",
  analysis_summary=response_text,
)
```

---

## Related

- [TaskAnalyzer AgentNode](../agent_sessions/task_analyzer.md)
- [TaskAnalyzerState](../state/information.md#taskanalyzerstate)
