# Query Analyst

> **File:** `docs/design/query-analyst.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft
> **Architecture reference:** [`../architecture/query-analyst.md`](../architecture/query-analyst.md), [`../architecture/task-classification.md`](../architecture/task-classification.md)
> **See also:** [`overview.md`](overview.md), [`loop-strategies.md`](loop-strategies.md), [`base-agent-wrapper.md`](base-agent-wrapper.md)

---

## Role

The Query Analyst classifies the user request by producing a `ModeDecision`
(`primary_agent`, `worker`, or `uncertain`) and a `ContextEnhancedQuery`.

---

## Wrapper Class

**File:** `tinycua/agents/query_analyst.py`

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import QueryAnalystConfig
from tinycua.constants.tools import QUERY_ANALYST_BASE_TOOLS
from tinycua.loops.query_analyst_loop import QueryAnalystLoop
from tinycua.loops.schema_validator import SchemaValidator
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

    async def run(
        self,
        user_query: str,
        chat_history: list[dict] | None = None,
        session_context: dict | None = None,
    ) -> dict[str, Any]:
        self.state.session_id = session_context.get("session_id") if session_context else None
        self.state.chat_history = chat_history or []
        input_msg = {
            "user_query": user_query,
            "chat_history": self.state.chat_history,
            "session_context": session_context or {},
        }
        raw = await self.agent.run(query=str(input_msg))
        result = SchemaValidator(validation_fn=validate_classification_output).validate(raw)
        self.state.mode_decision = ModeDecision(**result.get("mode_decision", {}))
        self.state.context_enhanced_query = ContextEnhancedQuery(**result.get("context_enhanced_query", {}))
        self.state.last_result = result
        return result
```

---

## Config

**File:** `tinycua/config/agents.py`

```python
@dataclass
class QueryAnalystConfig(AgentConfigBase):
    name: str = "query-analyst"
    instructions: str = QUERY_ANALYST_PROMPT
```

No agent-specific config fields beyond `extra_tools` (inherited from `AgentConfigBase`).
Classification labels are configured in `QUERY_ANALYST_BASE_TOOLS`.

---

## State

**File:** `tinycua/state/information.py`

```python
@dataclass
class QueryAnalystState(StateInformation):
    mode_decision: ModeDecision | None = None
    context_enhanced_query: ContextEnhancedQuery | None = None
    classification_score: float | None = None
```

---

## Loop

`QueryAnalystLoop` — extends SDK `BaseLoop` with default iteration behavior.
See [`loop-strategies.md`](loop-strategies.md#queryanalystloop).

---

## Tools

**File:** `tinycua/constants/tools.py`

```python
QUERY_ANALYST_BASE_TOOLS: list[Tool] = [
    ClassificationTool(labels=["primary_agent", "worker", "uncertain"]),
]
```

The `ClassificationTool` presents a list of classification labels to the agent.
The agent selects an index (`classify(mode_index=0)`) and the tool returns the label
at that index. To change classification labels, edit this constant — no prompt rewrite needed.

---

## Prompt Contract

**File:** `tinycua/agents/prompts.py`

The prompt must include:
- **Role**: Fast classification agent — scan, score, decide
- **Input contract**: `user_query`, `chat_history`, `session_context`
- **Output schema**: `ContextEnhancedQuery` + `ModeDecision` with fields: `mode`, `score`, `confidence`, `reasons`, `uncertain_next_action`
- **Scoring dimensions**: task complexity, context dependency, safety/risk
- **Guardrails (anti-laziness)**:
  - `primary_agent` rationale must explain why Worker decomposition is not needed
  - `worker` rationale must explain the decomposition benefit
  - `uncertain` mode must set `uncertain_next_action`
- **Tool usage**: Use `classify(mode_index=N)` to emit the classification verdict

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Classification labels in constant | `QUERY_ANALYST_BASE_TOOLS` | Code-level configuration; no runtime config needed |
| Index-based classification | Agent picks index, tool resolves label | Decouples labels from prompts; adding new modes doesn't require prompt edits |
| No `max_iterations=1` | Default SDK iteration | Prevents premature agent termination |
| No tools at loop level | Tool wired at wrapper level | Loop stays focused on execution strategy |
