# Task Analyzer

> **File:** `docs/design/agents/task_analyzer.md`
> **Package:** `tinycua.agents.task_analyzer`

---

## Wrapper Class

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import TaskAnalyzerConfig
from tinycua.constants.tools import TASK_ANALYZER_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.utility.schema_validator import SchemaValidator
from tinycua.state.information import TaskAnalyzerState
from tinycua.state import Task


class TaskAnalyzer(BaseAgentWrapper[TaskAnalyzerState]):
    """Task decomposition agent — ReActAgentLoop."""

    state: TaskAnalyzerState

    def __init__(self, config: TaskAnalyzerConfig):
        super().__init__(config, state_factory=TaskAnalyzerState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*TASK_ANALYZER_BASE_TOOLS, *self.config.extra_tools],
            loop=ReActAgentLoop(),
        )

    async def run(self, digested_information: dict) -> dict:
        self.state.last_query = {"digested_information": digested_information}
        raw = await self.agent.run(query=f"Analyze: {json.dumps(digested_information)}")
        result = SchemaValidator(validation_fn=validate_task_tree).validate(raw)
        self.state.task_tree = Task(**result)
        self.state.last_result = result
        return result
```

## Config

`TaskAnalyzerConfig` — `name="task-analyzer"`, `instructions=TASK_ANALYZER_PROMPT`.
See [`config/agents.md`](../config/agents.md#taskanalyzerconfig).

## State

`TaskAnalyzerState` — `task_tree: Task | None`.
See [`state/information.md`](../state/information.md#taskanalyzerstate).

## Loop

`ReActAgentLoop` — shared. See [`loops/react_agent.md`](../loops/react_agent.md).

## Tools

`TASK_ANALYZER_BASE_TOOLS = []`. Optional info tools via `config.extra_tools`.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No custom loop | `ReActAgentLoop` | Single input → single output |
| No inherent tools | Empty `BASE_TOOLS` | Optional tools injected via config |
