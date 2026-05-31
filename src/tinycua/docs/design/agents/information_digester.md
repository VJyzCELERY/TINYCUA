# Information Digester

> **File:** `docs/design/agents/information_digester.md`
> **Package:** `tinycua.agents.information_digester`

---

## Role

`InformationDigester` retrieves and digests information from the context-enhanced
query. It is **transient** (`is_transient = True`) — its output (DigestedInformation)
is passed directly to the Worker, not stored in the session. Nothing propagates on
termination.

---

## Orchestrator Class

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import InformationDigesterConfig
from tinycua.constants.tools import INFORMATION_DIGESTER_BASE_TOOLS
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
        # 1. Build instruction from base constant + dynamic context
        instructions = self.build_instruction({})

        # 2. Build query from domain input
        query = json.dumps(context_enhanced_query)

        # 3. Build SDK Agent per-call — no self.agent, no _build_agent()
        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=[*INFORMATION_DIGESTER_BASE_TOOLS, *self.config.extra_tools],
            loop=InformationDigestionLoop(
                state=self.state,
                max_iterations=self.config.max_iterations_override,
            ),
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
        self.state.digested_information = DigestedInformation(**result)
        self.state.last_result = result
```

---

## Config

`InformationDigesterConfig` — `name="information-digester"`, `instructions=INFORMATION_DIGESTER_INSTRUCTION`,
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


---


---


---

## See also

Prev : [`QueryAnalyst` Orchestrator](query_analyst.md) | Next : [`TaskAnalyzer`](task_analyzer.md)
