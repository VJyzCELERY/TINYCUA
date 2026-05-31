# QueryAnalystLoop

> **File:** `docs/design/loops/query_analyst_loop.md`
> **Package:** `tinycua.loops.query_analyst_loop`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

Classification loop for the Query Analyst: high-level context scan → multi-dimensional scoring →
one validated `ModeDecision` output. The agent uses `ClassificationTool` to emit its verdict.

Receives `QueryAnalystState` by reference for state tracking.

---

## Class Contract

**File:** `tinycua/loops/query_analyst_loop.py`

```python
from tinycua_sdk.agent.loop import BaseLoop
from tinycua.state.information import QueryAnalystState


class QueryAnalystLoop(BaseLoop):
    """Structured classification using SDK's normal BaseLoop behavior.

    Does NOT set max_iterations=1. Relies on prompt structure and
    ClassificationTool to produce one definitive classification result.
    """

    def __init__(self, state: QueryAnalystState):
        super().__init__()
        self.state = state

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        """Execute classification via SDK's BaseLoop.run()."""
        async for event in super().run(agent, messages, tools, override_instructions, stream=True):
            yield event
```

---

## Key Behaviors

- **Default iteration**: Uses SDK `BaseLoop` default — does NOT set `max_iterations=1`
- **One result, not one pass**: The agent may iterate internally (tool calling, re-reading context)
  but produces one validated output
- **ClassificationTool**: Wired at orchestrator level (via `QUERY_ANALYST_BASE_TOOLS`). Agent calls
  `classify(mode_index=N)` to emit verdict
- **Orchestrator post-processing**: After stream ends, `QueryAnalyst.run()` parses the
  accumulated text into `ModeDecision` and `ContextEnhancedQuery` typed objects

---

## Flow

```
user_query + chat_history + session_context
    → SDK Agent with ClassificationTool
        → LLM scans context, scores dimensions
         → LLM calls classify(mode_index=N)
         → ClassificationTool returns label at index N
    → Stream ends
    → Orchestrator parses accumulated text → ModeDecision (passthrough | worker | uncertain) + ContextEnhancedQuery
    → Stored in self.state
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No `max_iterations=1` | SDK default iteration | Prevents premature agent termination |
| ClassificationTool at orchestrator level | In `QUERY_ANALYST_BASE_TOOLS` | Loop stays focused on execution strategy; tools are an orchestrator concern |
| State via constructor | `QueryAnalystLoop(state=self.state)` | Direct reference for state access |
| No post-processing in loop | Orchestrator handles JSON parse | Loop controls execution; orchestrator manages typed state |


---


---


---

## See also

Prev : [`ReActAgentLoop`](react_agent.md) | Next : [`InformationDigestionLoop`](information_digestion_loop.md)


## Related

- [QueryAnalyst orchestrator](../agents/query_analyst.md)
- [ModeDecision produced by classification](../state/mode_decision.md)
- [ClassificationTool labels](../constants/tools.md)
