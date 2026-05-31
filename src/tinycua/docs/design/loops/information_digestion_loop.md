# InformationDigestionLoop

> **File:** `docs/design/loops/information_digestion_loop.md`
> **Package:** `tinycua.loops.information_digestion_loop`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

Iterative retrieval loop for the Information Digester with mandatory output
enforcement. The loop:

1. Runs iterative retrieval via SDK `BaseLoop` (search → evaluate gaps → repeat)
2. Tracks whether `digest_information` has been called at least once
3. Prevents the agent from stopping until `digest_information` has been called
4. Increments `self.state.retrieval_iterations` each cycle

Receives `InformationDigesterState` by reference.

---

## Class Contract

**File:** `tinycua/loops/information_digestion_loop.py`

```python
from tinycua_sdk.agent.loop import BaseLoop
from tinycua.state.information import InformationDigesterState


class InformationDigestionLoop(BaseLoop):
    """Iterative retrieval with mandatory digest_information call."""

    def __init__(
        self,
        state: InformationDigesterState,
        max_iterations: int | None = None,
    ):
        super().__init__()
        self.state = state
        self.max_iterations = max_iterations  # None → no iteration cap
        self._digest_called = False

    async def run(
        self, agent, messages, tools, override_instructions=None, stream=False
    ):
        """Execute iterative retrieval via SDK BaseLoop.

        - Tracks each tool_call event
        - Sets _digest_called = True when digest_information is called
        - Increments state.retrieval_iterations on each cycle
        """
        self.state.retrieval_iterations = 0
        self._digest_called = False

        async for event in super().run(
            agent, messages, tools, override_instructions, stream=True
        ):
            if event.get("type") == "response.tool_call":
                if event.get("tool_name") == "digest_information":
                    self._digest_called = True
                self.state.retrieval_iterations += 1
            yield event

    def can_stop(self, events: list[dict]) -> bool:
        """Override stop condition: must have called digest_information.

        Returns False until at least one digest_information call has
        been made, regardless of LLM-judged sufficiency.
        """
        if not self._digest_called:
            return False
        # Delegate to parent for sufficiency evaluation
        return super().can_stop(events)
```

---

## Stop Conditions

1. **LLM-judged sufficiency** (primary): Agent evaluates whether information gaps
   are sufficiently addressed.
2. **Mandatory digest call** (new): `_digest_called` must be `True` before stopping.
   Agent CANNOT exit without producing a `digest_information` call.
3. **`max_iterations` cap** (optional, default `None` = no limit): Hard stop even
   without a digest call. Prevents infinite loops when the agent fails to call
   the output tool.

---

## Flow

```
Input: ContextEnhancedQuery
  │
  ├─ 1. Write full parent context to .md cache
  │
  └─ 2. Agent loop (iterative):
       │
       ├── enhanced_context_retrieval(search_query) → internal agent → result
       │
       ├── LLM evaluates information sufficiency
       │
       ├── Needs more info? → loop back to enhanced_context_retrieval
       │
       ├── Sufficient? → MUST call digest_information(...)
       │
       └── digest_information called?
            ├── Yes + sufficient → STOP
            ├── Yes + not sufficient → loop back
            └── No:
                 ├── max_iterations not reached → loop back
                 └── max_iterations reached → STOP (forced)
```

On empty retrieval results: `DigestedInformation.known_gaps` should be populated
by the agent via the `digest_information` tool.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Mandatory digest call | `_digest_called` flag in loop | Guarantees structured output; agent can't "forget" to produce it |
| Stop deferral | `can_stop()` returns False until digest called | Clean override of BaseLoop behavior |
| Iteration tracking | `self.state.retrieval_iterations` incremented per cycle | Visible to orchestrator for debugging/monitoring |
| Max iterations as safety net | `max_iterations_override=None` by default | Agent normally stops on sufficiency; cap prevents infinite loops |
| State via constructor | `InformationDigestionLoop(state=self.state)` | Loop writes state directly; no event-passing overhead |
| Gap evaluation | Evaluated by LLM, not by loop | LLM understands semantic sufficiency better than heuristic rules |


---


---


---

## See also

Prev : [`QueryAnalystLoop`](query_analyst_loop.md) | Next : [`ResultReviewLoop`](result_review_loop.md)


## Related

- [InformationDigester orchestrator](../agents/information_digester.md)
- [DigestedInformation output](../state/digested_information.md)
- [enhanced_context_retrieval + digest_information tools](../tools/agent_calls.md)
