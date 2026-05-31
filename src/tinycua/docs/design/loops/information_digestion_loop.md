# InformationDigestionLoop

> **File:** `docs/design/loops/information_digestion_loop.md`
> **Package:** `tinycua.loops.information_digestion_loop`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

Iterative retrieval loop for the Information Digester: identify information gaps →
invoke Enhanced Context Retrieval → evaluate relevance → retrieve again or stop.
SDK `BaseLoop` handles the tool-calling iteration; this loop adds gap-evaluation logic.

---

## Class Contract

**File:** `tinycua/loops/information_digestion_loop.py`

```python
from tinycua_sdk.agent.loop import BaseLoop


class InformationDigestionLoop(BaseLoop):
    """Iterative retrieval with gap-evaluation between SDK iterations."""

    def __init__(self, max_iterations: int | None = None):
        super().__init__()
        if max_iterations is not None:
            self.max_iterations = max_iterations

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        """Execute iterative retrieval via SDK BaseLoop with gap evaluation."""
        # SDK BaseLoop handles: LLM → tool call → observe → repeat
        # After each iteration, check if LLM output indicates gaps are addressed
        # If gaps remain AND max_iterations not reached → continue
        # If gaps addressed OR max reached → validate and return DigestedInformation
        ...
```

---

## Stop Conditions

1. **LLM-judged sufficiency** (primary): Each iteration evaluates whether identified
   gaps are sufficiently addressed. Parsed from the LLM's output.
2. **`BaseLoop.max_iterations`** (hard cap, default 5): Prevents infinite loops.
   Configurable via `InformationDigesterConfig.max_iterations_override`.

Both must be satisfied — the loop stops when either condition is met.

---

## Flow

```
Input: ContextEnhancedQuery
    → LLM identifies information gaps
    → SDK Tool: enhanced_context_retrieval searches session context
    → LLM evaluates relevance
    ↓
    ┌─ Sufficient? ─→ Yes ─→ SchemaValidator → Output: DigestedInformation
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
| Max iterations configurable | `config.max_iterations_override` | Different deployments may want different limits |
| Gap evaluation in loop | Overridden `run()` | Loop is the execution strategy; gap evaluation is control flow |
