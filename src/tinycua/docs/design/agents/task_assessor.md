# Task Assessor

> **File:** `docs/design/agents/task_assessor.md`
> **Package:** `tinycua.agents.task_assessor`

---

## Wrapper Class

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import TaskAssessorConfig
from tinycua.constants.tools import TASK_ASSESSOR_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.utility.schema_validator import SchemaValidator
from tinycua.state.information import TaskAssessorState


class TaskAssessor(BaseAgentWrapper[TaskAssessorState]):
    """Task assessment agent — ReActAgentLoop."""

    state: TaskAssessorState

    def __init__(self, config: TaskAssessorConfig):
        super().__init__(config, state_factory=TaskAssessorState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*TASK_ASSESSOR_BASE_TOOLS, *self.config.extra_tools],
            loop=ReActAgentLoop(),
        )

    async def run(self, task_tree: dict, worker_config: dict) -> dict:
        self.state.last_query = {"task_tree": task_tree, "worker_config": worker_config}
        raw = await self.agent.run(query=json.dumps({"task_tree": task_tree, "worker_config": worker_config}))
        result = SchemaValidator(validation_fn=validate_task_selection).validate(raw)
        self.state.selected_task_ids = result.get("task_ids", [])
        self.state.last_result = result
        return result
```

## Config

`TaskAssessorConfig` — `name="task-assessor"`, `instructions=TASK_ASSESSOR_PROMPT`.
See [`config/agents.md`](../config/agents.md#taskassessorconfig).

## State

`TaskAssessorState` — `selected_task_ids: list[str]`.
See [`state/information.md`](../state/information.md#taskassessorstate).

## Loop

`ReActAgentLoop` — shared. See [`loops/react_agent.md`](../loops/react_agent.md).

## Tools

`TASK_ASSESSOR_BASE_TOOLS = []`. Assessment is a pure reasoning task.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No custom loop | `ReActAgentLoop` | Single input → single output |
| No tools | Empty `BASE_TOOLS` | Pure reasoning |
