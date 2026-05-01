# Stage 2: Agent Configuration & Creation — Design

## Architecture Decision: Collapse AgentDefinition into AgentConfig

The v1 codebase has both `AgentDefinition` and `AgentConfig`. For v2, we collapse this into a single `AgentConfig` that is the source of truth.

### Why?
- Having two config classes confuses consumers.
- `AgentDefinition` was bloated with sub-agent and backend features that are being removed.
- `AgentConfig` already has Pydantic validation.

### Migration:
1. Move any remaining useful fields from `AgentDefinition` into `AgentConfig`.
2. Delete `AgentDefinition` class.
3. `Agent` stores an `AgentConfig` instance internally.
4. `Agent` provides property proxies for convenience.

## Class Design

### `tinycua_sdk/agent/config.py`

```python
"""Agent configuration models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.tools.decorators import Tool
from tinycua_sdk.skills.models import Skill


class AgentPolicy(BaseModel):
    """Behavioral policy for an agent."""

    model_config = ConfigDict(frozen=True)

    max_tool_calls: int = 10
    parallel_tool_calls: bool = True


class AgentConfig(BaseModel):
    """Complete agent configuration."""

    name: str = "assistant"
    instructions: str = ""
    llm_model: LanguageModel = Field(default_factory=LanguageModel)
    tools: list[Tool] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    policy: AgentPolicy = Field(default_factory=AgentPolicy)
    metadata: dict = Field(default_factory=dict)
    loop: Any = None  # Will be BaseLoop | None after Stage 3
    tool_permissions: dict[str, Literal["allow", "ask", "deny"]] = Field(default_factory=dict)
    approval_workflow: Any = None  # Will be ApprovalWorkflow | None after Stage 3

    def to_config(self) -> dict:
        return {
            "name": self.name,
            "instructions": self.instructions,
            "llm_model": self.llm_model.to_dict(),
            "tools": [t.to_config() for t in self.tools],
            "skills": [s.to_dict() for s in self.skills],
            "policy": self.policy.model_dump(),
            "metadata": self.metadata,
            "tool_permissions": self.tool_permissions,
        }
```

### `tinycua_sdk/agent/agent.py`

```python
"""Agent public API."""
from __future__ import annotations

from typing import Literal

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.agent.executor import AgentExecutor
from tinycua_sdk.tools.decorators import Tool
from tinycua_sdk.skills.models import Skill


# Parameters removed in v2 that should be rejected
_OBSOLETE_PARAMS = frozenset({
    "system_prompt", "model", "provider", "base_url", "api_key",
    "mode", "backend_url", "backend_api_key", "backend_headers",
    "agent_id", "planning_prompt", "short_term_memory", "long_term_memory",
    "session_id", "sub_agents", "max_depth", "strip_thinking", "backend",
})


class Agent(AgentExecutor):
    """Stateless, fully runnable agent."""

    def __init__(
        self,
        name: str = "assistant",
        instructions: str = "",
        llm_model: LanguageModel | None = None,
        tools: list[Tool] | None = None,
        skills: list[Skill] | None = None,
        policy: AgentPolicy | None = None,
        metadata: dict | None = None,
        loop: Any = None,
        tool_permissions: dict[str, Literal["allow", "ask", "deny"]] | None = None,
        approval_workflow: Any = None,
        **kwargs: Any,
    ):
        # Reject obsolete parameters
        for key in kwargs:
            if key in _OBSOLETE_PARAMS:
                raise TypeError(
                    f"Agent() got an unexpected keyword argument '{key}'. "
                    f"This parameter has been removed in v2."
                )

        # Build config
        config = AgentConfig(
            name=name,
            instructions=instructions,
            llm_model=llm_model or LanguageModel(),
            tools=tools or [],
            skills=skills or [],
            policy=policy or AgentPolicy(),
            metadata=metadata or {},
            loop=loop,
            tool_permissions=tool_permissions or {},
            approval_workflow=approval_workflow,
        )

        super().__init__(config=config)

    # Proxies for convenience
    @property
    def name(self) -> str:
        return self.config.name

    @property
    def instructions(self) -> str:
        return self.config.instructions

    @property
    def llm_model(self) -> LanguageModel:
        return self.config.llm_model

    @property
    def tools(self) -> list[Tool]:
        return self.config.tools

    @property
    def skills(self) -> list[Skill]:
        return self.config.skills

    @property
    def policy(self) -> AgentPolicy:
        return self.config.policy

    @property
    def metadata(self) -> dict:
        return self.config.metadata

    @property
    def tool_permissions(self) -> dict[str, str]:
        return self.config.tool_permissions

    @tool_permissions.setter
    def tool_permissions(self, value: dict[str, str]) -> None:
        self.config.tool_permissions = value

    @property
    def approval_workflow(self) -> Any:
        return self.config.approval_workflow

    def add_tools(self, tool_or_list: Tool | list[Tool]) -> None:
        if isinstance(tool_or_list, list):
            self.config.tools.extend(tool_or_list)
        else:
            self.config.tools.append(tool_or_list)

    def add_skills(self, skill_or_list: Skill | list[Skill]) -> None:
        if isinstance(skill_or_list, list):
            self.config.skills.extend(skill_or_list)
        else:
            self.config.skills.append(skill_or_list)

    def to_config(self) -> dict:
        return self.config.to_config()
```

### `tinycua_sdk/agent/executor.py` (stub for Stage 3)

```python
"""Agent executor base."""
from __future__ import annotations

from typing import Any

from tinycua_sdk.agent.config import AgentConfig


class AgentExecutor:
    """Base class providing config storage. Execution logic added in Stage 3."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._cancelled = False

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("Agent.run() implemented in Stage 3")
```

## File Changes

| File | Action | Details |
|------|--------|---------|
| `agent/config.py` | Modify | Add `AgentConfig`, simplify `AgentPolicy`, remove `BackendConfig` refs |
| `agent/definition.py` | Delete | Collapse into `AgentConfig` |
| `agent/agent.py` | Rewrite | New constructor, property proxies, obsolete param rejection |
| `agent/executor.py` | Simplify | Keep as config holder + cancel stub |

## Data Flow

```
Consumer
    │
    ├──► Agent(name="x", llm_model=LanguageModel(...), ...)
    │       │
    │       ├──► validates kwargs against _OBSOLETE_PARAMS
    │       ├──► builds AgentConfig
    │       └──► passes AgentConfig to AgentExecutor.__init__
    │
    ├──► agent.add_tools(tool) ──► mutates config.tools
    ├──► agent.add_skills(skill) ──► mutates config.skills
    └──► agent.to_config() ──► returns serialized dict
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Obsolete parameter passed | `TypeError` with message naming the param |
| `add_tools` with non-Tool | `TypeError` (Pydantic validation on list) |
| `add_skills` with non-Skill | `TypeError` (Pydantic validation on list) |
