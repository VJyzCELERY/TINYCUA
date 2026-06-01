# InformationDigestionLoop

> **File:** `docs/design/loops/information_digestion_loop.md`
> **Package:** `tinycua.loops.information_digestion_loop`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

Iterative retrieval loop for the Information Digester. Runs the standard SDK
ReAct pattern: search → evaluate gaps → repeat. No custom stop conditions —
mandatory `digest_information` enforcement is handled at the **orchestrator level**
via the same retry pattern as QueryAnalyst and TaskAssessor.

Receives `InformationDigesterState` by reference — the loop increments
`self.state.retrieval_iterations` as it iterates.

---

## Class Contract

**File:** `tinycua/loops/information_digestion_loop.py`

```python
from tinycua_sdk.agent.loop import BaseLoop
from tinycua.state.information import InformationDigesterState


class InformationDigestionLoop(BaseLoop):
    """Iterative retrieval loop — no custom stop enforcement."""

    def __init__(
        self,
        state: InformationDigesterState,
        max_iterations: int | None = None,
    ):
        super().__init__()
        self.state = state
        self.max_iterations = max_iterations  # None → no iteration cap

    async def run(
        self, agent, messages, tools, override_instructions=None, stream=False
    ):
        """Execute iterative retrieval via SDK BaseLoop.

        Tracks tool calls and increments state.retrieval_iterations.
        Stops when: LLM-judged sufficiency, or max_iterations reached.
        """
        self.state.retrieval_iterations = 0

        async for event in super().run(
            agent, messages, tools, override_instructions, stream=True
        ):
            if event.get("type") == "response.tool_call":
                self.state.retrieval_iterations += 1
            yield event
```

---

## Stop Conditions

1. **LLM-judged sufficiency** (primary): Agent evaluates whether information gaps
   are sufficiently addressed.
2. **`max_iterations` cap** (optional, default `None` = no limit): Hard stop
   prevents infinite loops.

The orchestrator handles mandatory `digest_information` enforcement separately.
If the agent stops without calling `digest_information`, the orchestrator retries
with a follow-up query.

---

## Flow

```
Input: ContextEnhancedQuery
  │
  ├─ 1. Write full parent context to .md cache (orchestrator)
  │
  └─ 2. Agent loop (iterative):
       │
       ├── enhanced_context_retrieval(search_query) → internal agent → result
       │
       ├── LLM evaluates information sufficiency
       │
       ├── Needs more info? → loop back to enhanced_context_retrieval
       │
       └── Sufficient? → call digest_information(...) [required by orchestrator]
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No mandatory tool enforcement | Loop trusts agent; orchestrator handles retry | Loop stays simple; enforcement is consistent across all orchestrators |
| Iteration tracking | `self.state.retrieval_iterations` incremented per cycle | Visible to orchestrator for debugging/monitoring |
| Max iterations as safety net | `max_iterations_override=None` by default | Agent normally stops on sufficiency; cap prevents infinite loops |
| State via constructor | `InformationDigestionLoop(state=self.state)` | Loop writes state directly; no event-passing overhead |


---


---


---

## See also

Prev : [`QueryAnalystLoop`](query_analyst_loop.md) | Next : [`ResultReviewLoop`](result_review_loop.md)


## Related

- [InformationDigester orchestrator](../agents/information_digester.md)
- [DigestedInformation output](../state/digested_information.md)
- [enhanced_context_retrieval + digest_information tools](../tools/agent_calls.md)
