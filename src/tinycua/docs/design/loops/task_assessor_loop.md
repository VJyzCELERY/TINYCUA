# TaskAssessorLoop

> **File:** `docs/design/loops/task_assessor_loop.md`
> **Package:** `tinycua.loops.task_assessor_loop`
> **Last Updated:** 2026-06-01

---

## Role

`TaskAssessorLoop` is a custom SDK `BaseLoop` subclass for TaskAssessor. It enforces
the assessor classification (`analyze` or `stop`) while preserving the first assistant
response as the analysis text passed back to TaskAnalyzer.

---

## SDK Loop Shape

```text
class TaskAssessorLoop(BaseLoop):
    def __init__(self, session: Session, max_verdict_retries: int = 3):
        super().__init__()
        self.session = session
        self.max_verdict_retries = max_verdict_retries

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        ...  # SDK BaseLoop-compatible override
```

---

## Loop-Local Data

```text
analysis: str                 # first assistant response text
verdict: "analyze" | "stop" | None
retry_count: int
```

---

## Algorithm Inside `run(...)`

1. Run the SDK loop/LLM pass.
2. If `stream=True`, yield every SDK event outward.
3. Preserve the first assistant response as `analysis`.
4. Observe the classification tool result as `verdict`.
5. If verdict is missing, retry with an in-memory prompt requiring `analyze` or `stop`.
6. If verdict is still missing after retries, fallback to `stop` with `failure=1`.
7. Write `TaskAssessorState` and yield final-result event.

Retry responses must not replace the original `analysis` text.

---

## Final State

```text
TaskAssessorState(
  type="task_assessor",
  status="terminated",
  failure=0 or 1,
  verdict=verdict or "stop",
  analysis=analysis,
)
```

---

## Related

- [TaskAssessor AgentNode](../agent_node/task_assessor.md)
- [TaskAssessorState](../state/information.md#taskassessorstate)
