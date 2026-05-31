# Query Analyst

> **File:** `docs/design/agents/query_analyst.md`
> **Package:** `tinycua.agents.query_analyst`

---

## Orchestrator Class

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import QueryAnalystConfig
from tinycua.constants.tools import QUERY_ANALYST_BASE_TOOLS
from tinycua.constants.prompts import QUERY_ANALYST_PROMPT
from tinycua.loops.query_analyst_loop import QueryAnalystLoop
from tinycua.state.information import QueryAnalystState
from tinycua.state import ModeDecision, ContextEnhancedQuery


class QueryAnalyst(BaseAgentOrchestrator[QueryAnalystState]):
    """Query classification — QueryAnalystLoop with direct state reference."""

    config: QueryAnalystConfig

    def __init__(self, config: QueryAnalystConfig | None = None):
        if config is None:
            config = QueryAnalystConfig()
        self.config = config
        self.state = QueryAnalystState()

    async def run(
        self,
        user_query: str,
        chat_history: list[dict] | None = None,
        session_context: dict | None = None,
    ) -> AsyncIterator[dict]:
        """Run classification and yield all SDK stream events.

        Builds a fresh Agent per call with state injected into the loop.
        After the stream ends, parses the accumulated output into typed state.
        """
        self.state.session_id = session_context.get("session_id") if session_context else None
        self.state.chat_history = chat_history or []
        self.state.accumulated_text = []

        input_msg = json.dumps({
            "user_query": user_query,
            "chat_history": self.state.chat_history,
            "session_context": session_context or {},
        })

        agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*QUERY_ANALYST_BASE_TOOLS, *self.config.extra_tools],
            loop=QueryAnalystLoop(state=self.state),
        )

        async for event in agent.run(query=input_msg, stream=True):
            if event["type"] == "response.output_text.delta":
                self.state.accumulated_text.append(event["delta"])
            elif event["type"] == "response.usage":
                self.state.token_usage = event["usage"]
            yield event  # transparent — caller sees all SDK events

        # Stream ended — parse and store typed state
        raw = "".join(self.state.accumulated_text)
        result = json.loads(raw)
        self.state.mode_decision = ModeDecision(**result.get("mode_decision", {}))
        self.state.context_enhanced_query = ContextEnhancedQuery(
            **result.get("context_enhanced_query", {})
        )
        self.state.last_result = result
```

---

## Config

`QueryAnalystConfig` — `name="query-analyst"`, `instructions=QUERY_ANALYST_PROMPT`.
No agent-specific fields. See [`config/agents.md`](../config/agents.md#queryanalystconfig).

---

## State

`QueryAnalystState` — `mode_decision: ModeDecision | None`, `context_enhanced_query: ContextEnhancedQuery | None`,
`classification_score: float | None`. Plus base fields `accumulated_text`, `token_usage`.
See [`state/information.md`](../state/information.md#queryanalyststate).

---

## Loop

`QueryAnalystLoop(state=self.state)` — receives state by reference. Classification control flow.
No `max_iterations=1`. See [`loops/query_analyst_loop.md`](../loops/query_analyst_loop.md).

---

## Tools

`QUERY_ANALYST_BASE_TOOLS = [ClassificationTool(labels=["primary_agent", "worker", "uncertain"])]`.
See [`constants/tools.md`](../constants/tools.md).

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Labels in constant | `QUERY_ANALYST_BASE_TOOLS` | Code-level configuration; no runtime config needed |
| No `max_iterations=1` | Default SDK iteration | Prevents premature agent termination |
| Agent built per-call | `Agent(...)` in `run()` | Loop receives fresh state reference each call |
| State reference into loop | `QueryAnalystLoop(state=self.state)` | Loop reads/writes state directly — no custom events needed |
| Stream passthrough | `yield event` on all events | Caller sees token-by-token output, usage, tool calls |
