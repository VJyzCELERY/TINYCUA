# InformationDigestionLoop

> **File:** `docs/design/loops/information_digestion_loop.md`
> **Package:** `tinycua.loops.information_digestion_loop`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

Iterative retrieval loop for the Information Digester: identify information gaps →
invoke Enhanced Context Retrieval → evaluate relevance → retrieve again or stop.

Receives `InformationDigesterState` by reference — the loop increments
`self.state.retrieval_iterations` as it iterates.

---

## Class Contract

**File:** `tinycua/loops/information_digestion_loop.py`

```python
from tinycua_sdk.agent.loop import BaseLoop
from tinycua.state.information import InformationDigesterState


class InformationDigestionLoop(BaseLoop):
    """Iterative retrieval with gap-evaluation between SDK iterations."""

    def __init__(self, state: InformationDigesterState, max_iterations: int | None = None):
        super().__init__()
        self.state = state
        self.max_iterations = max_iterations  # None → no iteration cap

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        """Execute iterative retrieval via SDK BaseLoop with gap evaluation.

        SDK BaseLoop handles: LLM → tool call → observe → repeat.
        After each iteration, increment state.retrieval_iterations.
        Stop when gaps addressed or max_iterations reached.
        """
        self.state.retrieval_iterations = 0
        async for event in super().run(agent, messages, tools, override_instructions, stream=True):
            yield event
        # Loop can track iteration count here or inspect stream events
```

---

## Stop Conditions

1. **LLM-judged sufficiency** (primary): Each iteration evaluates whether identified
   gaps are sufficiently addressed. Parsed from the LLM's output.
2. **`max_iterations` cap** (optional, default `None` = no limit): Prevents infinite loops
   when explicitly set. Configurable via `InformationDigesterConfig.max_iterations_override`.

The loop stops when LLM-judged sufficiency is met, or when the `max_iterations` cap is
reached (if set).

---

## Flow

```
Input: ContextEnhancedQuery
    → LLM identifies information gaps
    → SDK Tool: enhanced_context_retrieval searches session context
    → LLM evaluates relevance
    → self.state.retrieval_iterations += 1
    ↓
    ┌─ Sufficient? ─→ Yes ─→ Stream ends → Orchestrator parses → DigestedInformation
    │ No
    │ max_iterations not reached
    └─→ loop back (identify remaining gaps)
```

On empty retrieval results: `DigestedInformation.known_gaps` is populated.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Stop on sufficiency + hard cap | LLM-judged + count-based | Context awareness + safety against infinite loops |
| Max iterations configurable | Constructor parameter from config | Different deployments may want different limits |
| State via constructor | `InformationDigestionLoop(state=self.state)` | Loop increments `retrieval_iterations` directly |
| Gap evaluation in loop | Overridden `run()` | Loop is the execution strategy; gap evaluation is control flow |


---


---


---

## See also

Prev : [`QueryAnalystLoop`](query_analyst_loop.md) | Next : [`ResultReviewLoop`](result_review_loop.md)


## Related

- [InformationDigester orchestrator](../agents/information_digester.md)
- [DigestedInformation output](../state/digested_information.md)
