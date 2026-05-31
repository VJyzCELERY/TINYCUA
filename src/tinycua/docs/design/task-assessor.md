# Task Assessor

> **File:** `docs/design/task-assessor.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft
> **Architecture reference:** [`../architecture/task-assessor.md`](../architecture/task-assessor.md)
> **See also:** [`overview.md`](overview.md), [`loop-strategies.md`](loop-strategies.md), [`base-agent-wrapper.md`](base-agent-wrapper.md)

---

## Role

The Task Assessor selects which tasks in a `Task` tree should be further decomposed
during Task Creation. Produces a list of task IDs selected for decomposition.

---

## Wrapper Class

**File:** `tinycua/agents/task_assessor.py`

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import TaskAssessorConfig
from tinycua.constants.tools import TASK_ASSESSOR_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.loops.schema_validator import SchemaValidator
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
        input_msg = json.dumps({"task_tree": task_tree, "worker_config": worker_config})
        raw = await self.agent.run(query=input_msg)
        result = SchemaValidator(validation_fn=validate_task_selection).validate(raw)
        self.state.selected_task_ids = result.get("task_ids", [])
        self.state.last_result = result
        return result
```

---

## Config

**File:** `tinycua/config/agents.py`

```python
@dataclass
class TaskAssessorConfig(AgentConfigBase):
    name: str = "task-assessor"
    instructions: str = TASK_ASSESSOR_PROMPT
```

---

## State

**File:** `tinycua/state/information.py`

```python
@dataclass
class TaskAssessorState(StateInformation):
    selected_task_ids: list[str] = field(default_factory=list)
```

---

## Loop

`ReActAgentLoop` — shared loop. See [`loop-strategies.md`](loop-strategies.md#reactagentloop).

---

## Tools

**File:** `tinycua/constants/tools.py`

```python
TASK_ASSESSOR_BASE_TOOLS: list[Tool] = []
```

No inherent tools. Assessment logic is in the prompt.

---

## Prompt Contract

**File:** `tinycua/agents/prompts.py`

The prompt must include:
- **Role**: Decomposition selection agent — assess tasks in a tree and select which need further breakdown
- **Input contract**: `Task` tree + `WorkerConfig`
- **Output schema**: `list[task_id]` — IDs of tasks selected for decomposition
- **Guardrails**: Only select tasks that are genuinely too complex for direct execution

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No custom loop | `ReActAgentLoop` | Single input → single output; no branching required |
| No tools by default | Empty `BASE_TOOLS` | Assessment is a pure reasoning task |
