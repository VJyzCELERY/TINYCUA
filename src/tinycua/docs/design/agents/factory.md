# Agent Factory

> **File:** `docs/design/agents/factory.md`
> **Package:** `tinycua.agents.factory`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`create_agent()` and `create_all_agents()` construct wrapper class instances from config
dataclasses. Each wrapper's `__init__` calls `_build_agent()` internally to compose the
SDK `Agent` with the correct loop, tools, model, and prompt.

---

## API

```python
from tinycua.config.types import AgentKind
from tinycua.config.agents import AgentConfigBase
from tinycua.agents.base import BaseAgentWrapper


def create_agent(
    kind: AgentKind,
    config: AgentConfigBase | None = None,
) -> BaseAgentWrapper:
    """Create one wrapper class instance from its config.

    If config is None, uses the default config for the given AgentKind.
    Returns the typed wrapper (e.g., QueryAnalyst), not a raw SDK Agent.
    """


def create_all_agents(
    config_overrides: dict[AgentKind, AgentConfigBase] | None = None,
) -> dict[AgentKind, BaseAgentWrapper]:
    """Create all seven internal agent wrappers + TinyCUA.

    config_overrides allows per-agent customization (extra tools, model, etc.)
    without modifying the default configs or wrapper code.
    """
```

---

## Usage

```python
from tinycua.agents.factory import create_agent, create_all_agents
from tinycua.config.types import AgentKind
from tinycua.config.agents import QueryAnalystConfig

# Create with defaults
analyst = create_agent(AgentKind.QUERY_ANALYST)
assert isinstance(analyst, QueryAnalyst)

# Create with overrides
custom_analyst = create_agent(
    AgentKind.QUERY_ANALYST,
    config=QueryAnalystConfig(
        model=custom_model,
        extra_tools=[logging_tool, monitoring_tool],
    ),
)

# Create all agents at once (for TinyCUA)
agents = create_all_agents()
assert len(agents) == 8  # 7 internal + TinyCUA
assert AgentKind.QUERY_ANALYST in agents
assert AgentKind.TINYCUA in agents
```

---

## Internal Flow

```
create_agent(AgentKind.QUERY_ANALYST, config)
  → Look up or use provided QueryAnalystConfig
  → Construct QueryAnalyst(config)
      → BaseAgentWrapper.__init__: self.config = config, self.state = QueryAnalystState()
      → _build_agent(): compose SDK Agent with loop, tools, model, prompt
  → Return wrapper instance
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Factory returns wrapper, not raw Agent | `BaseAgentWrapper` subclass | Callers interact through `run()`, never directly with SDK Agent |
| `config=None` uses defaults | Default config per agent kind | Simple creation path; overrides only when needed |
| `create_all_agents` includes TinyCUA | `AgentKind.TINYCUA` | Single call builds the full TinyCUA runtime |
