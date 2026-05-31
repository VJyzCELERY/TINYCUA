# Primary Agent

> **File:** `docs/design/agents/primary_agent.md`
> **Package:** `tinycua.agents.primary_agent`

---

## Orchestrator Class

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import PrimaryAgentConfig
from tinycua.constants.tools import PRIMARY_AGENT_BASE_TOOLS
from tinycua.constants.prompts import PRIMARY_AGENT_PROMPT
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.state.information import PrimaryAgentState


class PrimaryAgent(BaseAgentOrchestrator[PrimaryAgentState]):
    """Final synthesis — ReActAgentLoop with direct state reference."""

    config: PrimaryAgentConfig

    def __init__(self, config: PrimaryAgentConfig | None = None):
        if config is None:
            config = PrimaryAgentConfig()
        self.config = config
        self.state = PrimaryAgentState()

    async def run(self, input_data: dict) -> AsyncIterator[dict]:
        """input_data is ContextEnhancedQuery or WorkerResult."""
        self.state.last_query = {"input": input_data}
        self.state.accumulated_text = []

        input_msg = json.dumps(input_data)

        agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*PRIMARY_AGENT_BASE_TOOLS, *self.config.extra_tools],
            loop=ReActAgentLoop(state=self.state),
        )

        async for event in agent.run(query=input_msg, stream=True):
            if event["type"] == "response.output_text.delta":
                self.state.accumulated_text.append(event["delta"])
            elif event["type"] == "response.usage":
                self.state.token_usage = event["usage"]
            yield event

        raw = "".join(self.state.accumulated_text)
        result = json.loads(raw)
        self.state.final_response = result
        self.state.citations = result.get("citations", [])
        self.state.last_result = result
```

---

## Config

`PrimaryAgentConfig` — `name="primary-agent"`, `instructions=PRIMARY_AGENT_PROMPT`.
See [`config/agents.md`](../config/agents.md#primaryagentconfig).

---

## State

`PrimaryAgentState` — `final_response: dict`, `citations: list[str]`.
See [`state/information.md`](../state/information.md#primaryagentstate).

---

## Loop

`ReActAgentLoop(state=self.state)` — shared loop.
See [`loops/react_agent.md`](../loops/react_agent.md).

---

## Tools

`PRIMARY_AGENT_BASE_TOOLS = []`. Formatting/verification tools via `config.extra_tools`.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No custom loop | `ReActAgentLoop` | Single input → single output |
| Flexible input | Accepts CEQ or WorkerResult | Both modes converge here |
