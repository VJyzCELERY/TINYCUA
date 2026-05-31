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
from tinycua.constants.prompts import TASK_ASSESSOR_PROMPT
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
        self.state.last_query = {"task_tree": task_tree, "worker_config": worker_config}
        self.state.accumulated_text = []

        input_msg = json.dumps({"task_tree": task_tree, "worker_config": worker_config})

        agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*TASK_ASSESSOR_BASE_TOOLS, *self.config.extra_tools],
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
        self.state.selected_task_ids = result.get("task_ids", [])
        self.state.last_result = result
```

---

## Config

`TaskAssessorConfig` — `name="task-assessor"`, `instructions=TASK_ASSESSOR_PROMPT`.
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
