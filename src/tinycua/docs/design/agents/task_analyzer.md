# Task Analyzer

> **File:** `docs/design/agents/task_analyzer.md`
> **Package:** `tinycua.agents.task_analyzer`

---

## Orchestrator Class

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import TaskAnalyzerConfig
from tinycua.constants.tools import TASK_ANALYZER_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.state.information import TaskAnalyzerState
from tinycua.state import Task


class TaskAnalyzer(BaseAgentOrchestrator[TaskAnalyzerState]):
    """Task decomposition — ReActAgentLoop with direct state reference."""

    config: TaskAnalyzerConfig

    def __init__(self, config: TaskAnalyzerConfig | None = None):
        if config is None:
            config = TaskAnalyzerConfig()
        self.config = config
        self.state = TaskAnalyzerState()

    async def run(self, digested_information: dict) -> AsyncIterator[dict]:
        # 1. Build instruction from base constant + dynamic context
        instructions = self.build_instruction({})

        # 2. Build query from domain input
        query = f"Analyze: {json.dumps(digested_information)}"

        # 3. Build SDK Agent per-call — no self.agent, no _build_agent()
        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=[*TASK_ANALYZER_BASE_TOOLS, *self.config.extra_tools],
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
        self.state.task_tree = Task(**result)
        self.state.last_result = result
```

---

## Config

`TaskAnalyzerConfig` — `name="task-analyzer"`, `instructions=TASK_ANALYZER_INSTRUCTION`.
See [`config/agents.md`](../config/agents.md#taskanalyzerconfig).

---

## State

`TaskAnalyzerState` — `task_tree: Task | None`.
See [`state/information.md`](../state/information.md#taskanalyzerstate).

---

## Loop

`ReActAgentLoop(state=self.state)` — shared loop with state reference for logging/telemetry.
See [`loops/react_agent.md`](../loops/react_agent.md).

---

## Tools

`TASK_ANALYZER_BASE_TOOLS = []`. Optional info tools via `config.extra_tools`.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No custom loop | `ReActAgentLoop` | Single input → single output |
| Shared loop with state | `ReActAgentLoop(state=self.state)` | Consistency; state reference for telemetry |


---

## See also

Prev : [`InformationDigester`](information_digester.md) | Next : [`TaskAssessor`](task_assessor.md)
