# Primary Agent

> **File:** `docs/design/agents/primary_agent.md`
> **Package:** `tinycua.agents.primary_agent`

---

## Role

`PrimaryAgent` is the final synthesis orchestrator. It serves two roles:

1. **Default passthrough target** — when QueryAnalyst returns passthrough mode and no
   active task exists, the user query is routed directly to PrimaryAgent.
2. **Worker-chain terminal** — after the Worker chain completes (TaskCreator →
   TaskExecutor → ResultReviewer), the aggregated worker result is passed to
   PrimaryAgent for final synthesis.

When activated, the parent orchestrator calls `add_child(primary.session)` first,
then terminates the previous child. This ensures there is never a gap where
no active agent exists.

---

## Orchestrator Class

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import PrimaryAgentConfig
from tinycua.constants.tools import PRIMARY_AGENT_BASE_TOOLS
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

        # 1. Build instruction from base constant + dynamic context
        instructions = self.build_instruction({})

        # 2. Build query from domain input
        query = json.dumps(input_data)

        # 3. Build SDK Agent per-call — no self.agent, no _build_agent()
        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=[*PRIMARY_AGENT_BASE_TOOLS, *self.config.extra_tools],
            loop=ReActAgentLoop(state=self.state),
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
        self.state.final_response = result
        self.state.citations = result.get("citations", [])
        self.state.last_result = result
```

---

## Config

`PrimaryAgentConfig` — `name="primary-agent"`, `instructions=PRIMARY_AGENT_INSTRUCTION`.
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


---


---


---

## See also

Prev : [`ResultReviewer`](result_reviewer.md) | Next : [`TinyCUA` External Orchestrator](tinycua.md)
