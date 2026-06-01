# ResultReviewLoop

> **File:** `docs/design/loops/result_review_loop.md`
> **Package:** `tinycua.loops.result_review_loop`
> **Last Updated:** 2026-06-01

---

## Role

`ResultReviewLoop` is a custom SDK `BaseLoop` subclass for ResultReviewer. It lets the
SDK loop access `Session`, preserves stream events, observes reviewer tool usage,
handles retry prompts for missing review classification when appropriate, writes
`ResultReviewerState`, and supports non-terminal open-question behavior.

---

## SDK Loop Shape

```text
class ResultReviewLoop(ReActLoop):
    def __init__(self, session: Session, max_review_retries: int = 3):
        super().__init__(session)
        self.session = session
        self.max_review_retries = max_review_retries

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        ...  # SDK BaseLoop-compatible override
```

---

## Loop-Local Data

```text
decision: "accept" | "retry" | "replan" | None
reason: str
context_updates: list[dict]
retry_instructions: str | None
retry_count: int
failure: int
```

No confidence score is required unless the review tool contract later defines one.

---

## Algorithm Inside `run(...)`

1. Run the SDK loop/LLM pass with reviewer tools.
2. If `stream=True`, yield every SDK event outward.
3. Observe reviewer classification tool result as `decision`.
4. Observe `ReviewContextUpdateTool` and `UpdateActiveTaskResult` results.
5. If decision is `accept`, `retry`, or `replan`, write terminal `ResultReviewerState`
   and yield final-result event.
6. If the response ends as an open question / no decision, leave the reviewer active
   and do not emit a terminal final-result event.
7. If decision is missing but the response is not an open question, optionally retry
   with an in-memory prompt asking for one of `accept`, `retry`, `replan`.

---

## Decision Handling

| Decision | Loop behavior |
|----------|---------------|
| `accept` | record accepted result/context updates; terminal |
| `retry` | ensure retry instructions/context are present; Worker routes back to TaskExecutor |
| `replan` | signal Worker to route TaskAssessor → TaskAnalyzer |
| `None` + open question | keep node active; no terminal final event |

---

## Final State

```text
ResultReviewerState(
  type="result_reviewer",
  status="terminated" | "running" | "blocked",
  failure=failure,
  decision=decision,
  reason=reason,
  context_updates=context_updates,
  retry_instructions=retry_instructions,
)
```

---

## Related

- [ResultReviewer AgentNode](../agent_node/result_reviewer.md)
- [ResultReviewerState](../state/information.md#resultreviewerstate)
