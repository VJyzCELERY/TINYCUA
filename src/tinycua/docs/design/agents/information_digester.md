# Information Digester

> **File:** `docs/design/agents/information_digester.md`
> **Package:** `tinycua.agents.information_digester`

---

## Wrapper Class

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import InformationDigesterConfig
from tinycua.constants.tools import INFORMATION_DIGESTER_BASE_TOOLS
from tinycua.loops.information_digestion_loop import InformationDigestionLoop
from tinycua.utility.schema_validator import SchemaValidator
from tinycua.state.information import InformationDigesterState
from tinycua.state import DigestedInformation


class InformationDigester(BaseAgentWrapper[InformationDigesterState]):
    """Information digestion agent — InformationDigestionLoop."""

    state: InformationDigesterState

    def __init__(self, config: InformationDigesterConfig):
        super().__init__(config, state_factory=InformationDigesterState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*INFORMATION_DIGESTER_BASE_TOOLS, *self.config.extra_tools],
            loop=InformationDigestionLoop(max_iterations=self.config.max_iterations_override),
        )

    async def run(self, context_enhanced_query: dict) -> dict:
        self.state.last_query = {"context_enhanced_query": context_enhanced_query}
        raw = await self.agent.run(query=json.dumps(context_enhanced_query))
        result = SchemaValidator(validation_fn=validate_digested_information).validate(raw)
        self.state.digested_information = DigestedInformation(**result)
        self.state.last_result = result
        return result
```

## Config

`InformationDigesterConfig` — `name="information-digester"`, `instructions=INFORMATION_DIGESTER_PROMPT`, `max_iterations_override: int | None`.
See [`config/agents.md`](../config/agents.md#informationdigesterconfig).

## State

`InformationDigesterState` — `digested_information: DigestedInformation | None`, `retrieval_iterations: int`.
See [`state/information.md`](../state/information.md#informationdigesterstate).

## Loop

`InformationDigestionLoop` — iterative retrieval with gap evaluation.
See [`loops/information_digestion_loop.md`](../loops/information_digestion_loop.md).

## Tools

`INFORMATION_DIGESTER_BASE_TOOLS = [enhanced_context_retrieval]`.
See [`constants/tools.md`](../constants/tools.md).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Max iterations configurable | `config.max_iterations_override` | Different deployment needs |
| Empty results → known_gaps | Loop populates `DigestedInformation.known_gaps` | Explicit gap documentation |
