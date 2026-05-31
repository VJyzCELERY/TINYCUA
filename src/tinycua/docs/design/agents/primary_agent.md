# Primary Agent

> **File:** `docs/design/agents/primary_agent.md`
> **Package:** `tinycua.agents.primary_agent`

---

## Wrapper Class

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import PrimaryAgentConfig
from tinycua.constants.tools import PRIMARY_AGENT_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.utility.schema_validator import SchemaValidator
from tinycua.state.information import PrimaryAgentState


class PrimaryAgent(BaseAgentWrapper[PrimaryAgentState]):
    """Final synthesis agent — ReActAgentLoop."""

    state: PrimaryAgentState

    def __init__(self, config: PrimaryAgentConfig):
        super().__init__(config, state_factory=PrimaryAgentState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*PRIMARY_AGENT_BASE_TOOLS, *self.config.extra_tools],
            loop=ReActAgentLoop(),
        )

    async def run(self, input_data: dict) -> dict:
        """input_data is ContextEnhancedQuery or WorkerResult."""
        self.state.last_query = {"input": input_data}
        raw = await self.agent.run(query=json.dumps(input_data))
        result = SchemaValidator(validation_fn=validate_final_response).validate(raw)
        self.state.final_response = result
        self.state.citations = result.get("citations", [])
        self.state.last_result = result
        return result
```

## Config

`PrimaryAgentConfig` — `name="primary-agent"`, `instructions=PRIMARY_AGENT_PROMPT`.
See [`config/agents.md`](../config/agents.md#primaryagentconfig).

## State

`PrimaryAgentState` — `final_response: dict`, `citations: list[str]`.
See [`state/information.md`](../state/information.md#primaryagentstate).

## Loop

`ReActAgentLoop` — shared. See [`loops/react_agent.md`](../loops/react_agent.md).

## Tools

`PRIMARY_AGENT_BASE_TOOLS = []`. Formatting/verification tools via `config.extra_tools`.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No custom loop | `ReActAgentLoop` | Single input → single output |
| Flexible input | Accepts CEQ or WorkerResult | Both modes converge here |
