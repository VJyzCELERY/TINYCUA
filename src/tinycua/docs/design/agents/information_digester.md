# Information Digester

> **File:** `docs/design/agents/information_digester.md`
> **Package:** `tinycua.agents.information_digester`

---

## Orchestrator Class

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import InformationDigesterConfig
from tinycua.constants.tools import INFORMATION_DIGESTER_BASE_TOOLS
from tinycua.constants.prompts import INFORMATION_DIGESTER_PROMPT
from tinycua.loops.information_digestion_loop import InformationDigestionLoop
from tinycua.state.information import InformationDigesterState
from tinycua.state import DigestedInformation


class InformationDigester(BaseAgentOrchestrator[InformationDigesterState]):
    """Information digestion — InformationDigestionLoop with direct state reference."""

    config: InformationDigesterConfig

    def __init__(self, config: InformationDigesterConfig | None = None):
        if config is None:
            config = InformationDigesterConfig()
        self.config = config
        self.state = InformationDigesterState()

    async def run(self, context_enhanced_query: dict) -> AsyncIterator[dict]:
        self.state.last_query = {"context_enhanced_query": context_enhanced_query}
        self.state.accumulated_text = []

        input_msg = json.dumps(context_enhanced_query)

        agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*INFORMATION_DIGESTER_BASE_TOOLS, *self.config.extra_tools],
            loop=InformationDigestionLoop(
                state=self.state,
                max_iterations=self.config.max_iterations_override,
            ),
        )

        async for event in agent.run(query=input_msg, stream=True):
            if event["type"] == "response.output_text.delta":
                self.state.accumulated_text.append(event["delta"])
            elif event["type"] == "response.usage":
                self.state.token_usage = event["usage"]
            yield event

        raw = "".join(self.state.accumulated_text)
        result = json.loads(raw)
        self.state.digested_information = DigestedInformation(**result)
        self.state.last_result = result
```

---

## Config

`InformationDigesterConfig` — `name="information-digester"`, `instructions=INFORMATION_DIGESTER_PROMPT`,
`max_iterations_override: int | None`. See [`config/agents.md`](../config/agents.md#informationdigesterconfig).

---

## State

`InformationDigesterState` — `digested_information: DigestedInformation | None`,
`retrieval_iterations: int`.
See [`state/information.md`](../state/information.md#informationdigesterstate).

---

## Loop

`InformationDigestionLoop(state=self.state, max_iterations=...)` — iterative retrieval
with gap evaluation. The loop increments `self.state.retrieval_iterations` internally.
See [`loops/information_digestion_loop.md`](../loops/information_digestion_loop.md).

---

## Tools

`INFORMATION_DIGESTER_BASE_TOOLS = [enhanced_context_retrieval]`.
See [`constants/tools.md`](../constants/tools.md).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Max iterations configurable | `config.max_iterations_override` | Different deployment needs |
| Empty results → known_gaps | Loop populates `DigestedInformation.known_gaps` | Explicit gap documentation |
| State reference into loop | `InformationDigestionLoop(state=self.state)` | Loop tracks `retrieval_iterations` directly |
