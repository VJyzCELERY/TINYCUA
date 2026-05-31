# Query Analyst

> **File:** `docs/design/agents/query_analyst.md`
> **Package:** `tinycua.agents.query_analyst`

---

## Orchestrator Class

```python
import json
from collections.abc import AsyncItevrator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import QueryAnalystConfig
from tinycua.constants.tools import QUERY_ANALYST_BASE_TOOLS
from tinycua.loops.query_analyst_loop import QueryAnalystLoop
from tinycua.state.information import QueryAnalystState
from tinycua.state import ModeDecision, ContextEnhancedQuery


class QueryAnalyst(BaseAgentOrchestrator[QueryAnalystState]):
    """Query classification — transient agent whose output is NOT stored.

    Always called first by TinyCUA. Decides between:
      - Passthrough: route to PrimaryAgent (no active task) or active agent
      - Worker: abort children + task, spawn fresh InfoDigester → Worker chain
    """

    config: QueryAnalystConfig

    def __init__(self, config: QueryAnalystConfig | None = None):
        if config is None:
            config = QueryAnalystConfig()
        self.config = config
        self.state = QueryAnalystState()

    async def run(
        self,
        user_query: str,
        session: Session,
    ) -> AsyncIterator[dict]:
        # 1. Build instruction from base constant + dynamic context
        instructions = self.build_instruction({
            "session": session,
        })

        # 2. Build query from domain input
        query = json.dumps({
            "user_query": user_query,
            "session_context": session.get_messages() if session else None,
        })

        # 3. Build SDK Agent per-call — no self.agent, no _build_agent()
        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=[*QUERY_ANALYST_BASE_TOOLS, *self.config.extra_tools],
            loop=QueryAnalystLoop(state=self.state),
        )

        # 4. Iterate stream — accumulate text, yield everything to caller
        text_parts: list[str] = []
        async for event in agent.run(query=query, stream=True):
            if event["type"] == "response.output_text.delta":
                text_parts.append(event["delta"])
            yield event

        # 5. After stream ends — parse and store typed state
        raw = "".join(text_parts)
        result = json.loads(raw)
        self.state.mode_decision = ModeDecision(**result.get("mode_decision", {}))
        self.state.context_enhanced_query = ContextEnhancedQuery(
            **result.get("context_enhanced_query", {})
        )
        self.state.last_result = result
```

---

## Config

`QueryAnalystConfig` — `name="query-analyst"`, `instructions=QUERY_ANALYST_INSTRUCTION`.
No agent-specific fields. See [`config/agents.md`](../config/agents.md#queryanalystconfig).

---

## State

`QueryAnalystState` — `mode_decision: ModeDecision | None`, `context_enhanced_query: ContextEnhancedQuery | None`,
`classification_score: float | None`.
See [`state/information.md`](../state/information.md#queryanalyststate).

---

## Loop

`QueryAnalystLoop(state=self.state)` — receives state by reference. Classification control flow.
No `max_iterations=1`. See [`loops/query_analyst_loop.md`](../loops/query_analyst_loop.md).

---

## Tools

`QUERY_ANALYST_BASE_TOOLS = [ClassificationTool(labels=["passthrough", "worker", "uncertain"])]`.
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
| Transient session | `is_transient = True` | Output not stored in chat_history or session_context |
| Passthrough sub-routing | `get_active_session()` determines target | No active task → PrimaryAgent; active task → active agent |
| Worker mode aborts | Terminate all children, `session.task = None` | Fresh start for the worker chain |


---


---


---

## See also

Prev : [Orchestrator Factory](factory.md) | Next : [`InformationDigester`](information_digester.md)
