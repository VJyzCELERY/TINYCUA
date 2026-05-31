# Query Analyst

> **File:** `docs/design/agents/query_analyst.md`
> **Package:** `tinycua.agents.query_analyst`

---

## Wrapper Class

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import QueryAnalystConfig
from tinycua.constants.tools import QUERY_ANALYST_BASE_TOOLS
from tinycua.loops.query_analyst_loop import QueryAnalystLoop
from tinycua.utility.schema_validator import SchemaValidator
from tinycua.state.information import QueryAnalystState
from tinycua.state import ModeDecision, ContextEnhancedQuery


class QueryAnalyst(BaseAgentWrapper[QueryAnalystState]):
    """Query classification agent — QueryAnalystLoop."""

    state: QueryAnalystState

    def __init__(self, config: QueryAnalystConfig):
        super().__init__(config, state_factory=QueryAnalystState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*QUERY_ANALYST_BASE_TOOLS, *self.config.extra_tools],
            loop=QueryAnalystLoop(),
        )

    async def run(self, user_query: str, chat_history=None, session_context=None) -> dict:
        self.state.session_id = session_context.get("session_id") if session_context else None
        self.state.chat_history = chat_history or []
        input_msg = {"user_query": user_query, "chat_history": self.state.chat_history, "session_context": session_context or {}}
        raw = await self.agent.run(query=str(input_msg))
        result = SchemaValidator(validation_fn=validate_classification_output).validate(raw)
        self.state.mode_decision = ModeDecision(**result.get("mode_decision", {}))
        self.state.context_enhanced_query = ContextEnhancedQuery(**result.get("context_enhanced_query", {}))
        self.state.last_result = result
        return result
```

## Config

`QueryAnalystConfig` — `name="query-analyst"`, `instructions=QUERY_ANALYST_PROMPT`.
No agent-specific fields. See [`config/agents.md`](../config/agents.md#queryanalystconfig).

## State

`QueryAnalystState` — `mode_decision: ModeDecision | None`, `context_enhanced_query: ContextEnhancedQuery | None`, `classification_score: float | None`.
See [`state/information.md`](../state/information.md#queryanalyststate).

## Loop

`QueryAnalystLoop` — classification control flow. No `max_iterations=1`.
See [`loops/query_analyst_loop.md`](../loops/query_analyst_loop.md).

## Tools

`QUERY_ANALYST_BASE_TOOLS = [ClassificationTool(labels=["primary_agent", "worker", "uncertain"])]`.
See [`constants/tools.md`](../constants/tools.md).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Labels in constant, not config | `QUERY_ANALYST_BASE_TOOLS` | Code-level configuration; no runtime config needed |
| No `max_iterations=1` | Default SDK iteration | Prevents premature agent termination |
