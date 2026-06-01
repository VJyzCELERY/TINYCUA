# TaskAnalyzerLoop

> **File:** `docs/design/loops/task_analyzer_loop.md`
> **Package:** `tinycua.loops.task_analyzer_loop`
> **Last Updated:** 2026-06-01

---

## Role

`TaskAnalyzerLoop` is a custom SDK `BaseLoop` subclass for TaskAnalyzer. It gives the
SDK loop access to `Session`, passes through stream events, observes task tool activity
for audit/failure handling, and writes `TaskAnalyzerState` from the final assistant
summary.

Task tree mutation belongs to task tools operating on `session.task`. The loop should
not parse or reconstruct a task tree from the assistant text.

---

## SDK Loop Shape

```text
class TaskAnalyzerLoop(ReActLoop):
    def __init__(self, session: Session):
        super().__init__(session)
        self.session = session

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        ...  # SDK BaseLoop-compatible override
```

---

## Loop-Local Data

```text
analysis_summary: str
failure: int
```

Tool calls/results may be observed for audit and failure accounting, but the final
state only needs the summary and failure count.

---

## Algorithm Inside `run(...)`

1. Run the SDK loop/LLM pass with task tools available.
2. If `stream=True`, yield SDK events outward as they are produced.
3. Observe task tool failures, if any, to increment `failure`.
4. Capture final assistant text as `analysis_summary`.
5. Append the summary and observed tool metadata according to session policy.
6. Write `TaskAnalyzerState` and yield final-result event.

---

## Final State

```text
TaskAnalyzerState(
  type="task_analyzer",
  status="terminated",
  failure=failure,
  analysis_summary=analysis_summary,
)
```

---

## Related

- [TaskAnalyzer AgentNode](../agent_node/task_analyzer.md)
- [TaskAnalyzerState](../state/information.md#taskanalyzerstate)
