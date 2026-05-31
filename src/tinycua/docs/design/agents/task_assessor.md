# Task Assessor

> **File:** `docs/design/agents/task_assessor.md`
> **Package:** `tinycua.agents.task_assessor`

---

## Orchestrator Class

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import TaskAssessorConfig
from tinycua.constants.tools import TASK_ASSESSOR_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.state.information import TaskAssessorState


class TaskAssessor(BaseAgentOrchestrator[TaskAssessorState]):
    """Task assessment — ReActAgentLoop with direct state reference."""

    config: TaskAssessorConfig

    def __init__(self, config: TaskAssessorConfig | None = None):
        if config is None:
            config = TaskAssessorConfig()
        self.config = config
        self.state = TaskAssessorState()

    async def run(self, task_tree: dict, worker_config: dict) -> AsyncIterator[dict]:
        # 1. Build instruction from base constant + dynamic context
        instructions = self.build_instruction({})

        # 2. Build query from domain input
        query = json.dumps({"task_tree": task_tree, "worker_config": worker_config})

        # 3. Build SDK Agent per-call — no self.agent, no _build_agent()
        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=[*TASK_ASSESSOR_BASE_TOOLS, *self.config.extra_tools],
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
        self.state.selected_task_ids = result.get("task_ids", [])
        self.state.last_result = result
```

---

## Config

`TaskAssessorConfig` — `name="task-assessor"`, `instructions=TASK_ASSESSOR_INSTRUCTION`.
See [`config/agents.md`](../config/agents.md#taskassessorconfig).

---

## State

`TaskAssessorState` — `selected_task_ids: list[str]`.
See [`state/information.md`](../state/information.md#taskassessorstate).

---

## Loop

`ReActAgentLoop(state=self.state)` — shared loop with state reference.
See [`loops/react_agent.md`](../loops/react_agent.md).

---

## Tools

`TASK_ASSESSOR_BASE_TOOLS = []`. Assessment is a pure reasoning task.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No custom loop | `ReActAgentLoop` | Single input → single output |
| No tools | Empty `BASE_TOOLS` | Pure reasoning |


---

## See also

Prev : [`TaskAnalyzer`](task_analyzer.md) | Next : [`TaskExecutor`](task_executor.md)
