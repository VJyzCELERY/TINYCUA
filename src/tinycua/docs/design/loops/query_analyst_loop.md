# QueryAnalystLoop

> **File:** `docs/design/loops/query_analyst_loop.md`
> **Package:** `tinycua.loops.query_analyst_loop`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

Classification loop for the Query Analyst: high-level context scan → multi-dimensional scoring →
one validated `ModeDecision` output. The agent uses `ClassificationTool` to emit its verdict
by selecting a mode index.

---

## Class Contract

**File:** `tinycua/loops/query_analyst_loop.py`

```python
from tinycua_sdk.agent.loop import BaseLoop


class QueryAnalystLoop(BaseLoop):
    """Structured classification using SDK's normal BaseLoop behavior.

    Does NOT set max_iterations=1. Relies on prompt structure and schema
    validation to produce one definitive classification result.
    """

    def __init__(self):
        super().__init__()  # SDK default iteration; no forced single-pass

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        """Execute classification via SDK's BaseLoop.run()."""
        return await super().run(agent, messages, tools, override_instructions, stream)
```

---

## Key Behaviors

- **Default iteration**: Uses SDK `BaseLoop` default — does NOT set `max_iterations=1`
- **One result, not one pass**: The agent may iterate internally (tool calling, re-reading context)
  but produces one validated `ContextEnhancedQuery` + `ModeDecision`
- **ClassificationTool**: Wired at wrapper level (via `QUERY_ANALYST_BASE_TOOLS`). Agent calls
  `classify(mode_index=N)` to emit verdict; tool resolves the index to a label
- **Schema validation**: `SchemaValidator` on the wrapper validates the output

---

## Why Not `max_iterations=1`?

Forcing a one-pass loop can make the agent stop immediately before the SDK loop has room
to complete normal execution (message construction, system prompt processing, tool response
parsing). Classification relies on prompt design and schema validation to produce one result.

---

## Flow

```
user_query + chat_history + session_context
    → SDK Agent with ClassificationTool
        → LLM scans context, scores dimensions
        → LLM calls classify(mode_index=N)
        → ClassificationTool returns label at index N
    → SchemaValidator validates {context_enhanced_query, mode_decision}
    → Wrapper stores result in self.state
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No `max_iterations=1` | SDK default iteration | Prevents premature agent termination |
| ClassificationTool at wrapper level | In `QUERY_ANALYST_BASE_TOOLS` | Loop stays focused on execution strategy; tools are a wrapper concern |
| Schema validation in wrapper | `SchemaValidator` in `run()` | Separation of concerns: loop executes, wrapper validates |
