# Task Creator

> **File:** `docs/design/agents/task_creator.md`
> **Package:** `tinycua.agents.task_creator`

---

## Orchestrator Class

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import TaskCreatorConfig
from tinycua.constants.tools import TASK_CREATOR_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.state.information import TaskCreatorState
from tinycua.state import DigestedInformation, Task


class TaskCreator(BaseAgentOrchestrator[TaskCreatorState]):
    """Wraps TaskAnalyzer → TaskAssessor, returns aggregated task tree.

    Called by the Worker orchestrator via call_task_creator tool.
    Internally delegates to TaskAnalyzer (decomposition) and TaskAssessor
    (selection), then returns the validated task tree.
    """

    config: TaskCreatorConfig

    def __init__(self, config: TaskCreatorConfig | None = None):
        if config is None:
            config = TaskCreatorConfig()
        self.config = config
        self.state = TaskCreatorState()

    async def run(
        self,
        digested_information: DigestedInformation,
    ) -> AsyncIterator[dict]:
        # 1. Build instruction from base constant + dynamic context
        instructions = self.build_instruction({})

        # 2. Build query from domain input
        query = json.dumps({
            "digested_information": digested_information.to_dict(),
        })

        # 3. Build SDK Agent per-call — no self.agent, no _build_agent()
        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=[*TASK_CREATOR_BASE_TOOLS, *self.config.extra_tools],
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
        self.state.task_tree = Task(**result.get("task_tree", {}))
        self.state.selected_task_ids = result.get("selected_task_ids", [])
        self.state.last_result = result
```

---

## Config

`TaskCreatorConfig` — `name="task-creator"`, `instructions=TASK_CREATOR_INSTRUCTION`.
See [`config/agents.md`](../config/agents.md#taskcreatorconfig).

---

## State

`TaskCreatorState` — `task_tree: Task | None`, `selected_task_ids: list[str]`.
See [`state/information.md`](../state/information.md#taskcreatorstate).

---

## Loop

`ReActAgentLoop(state=self.state)` — shared loop. Single input (DigestedInformation) →
single output (validated task tree with selections).

---

## Tools

`TASK_CREATOR_BASE_TOOLS = []`. The agent orchestrates internally via prompt structure.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Wraps two agents | TaskAnalyzer + TaskAssessor internally | Worker calls one tool instead of two; cleaner orchestration |
| Shared ReAct loop | `ReActAgentLoop` | Single input → single output |
| Agent built per-call | `Agent(...)` in `run()` | Follows BaseAgentOrchestrator pattern |


---


---


---

## See also

Prev : [`TaskAssessor`](task_assessor.md) | Next : [`TaskExecutor`](task_executor.md)


## Related

- [Wraps TaskAnalyzer internally](task_analyzer.md)
- [Wraps TaskAssessor internally](task_assessor.md)
- [Aggregated Task tree output](../state/task.md)
- [Exposed as call_task_creator tool](../tools/agent_calls.md)
