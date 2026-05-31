# Orchestrator Factory

> **File:** `docs/design/agents/factory.md`
> **Package:** `tinycua.agents.factory`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`create_orchestrator()` and `create_all_orchestrators()` construct typed orchestrator
instances from config dataclasses. Each orchestrator stores persistent config and
initializes its typed `StateInformation`. No SDK `Agent` is created at this point —
that happens inside each orchestrator's `run()` method.

---

## API

```python
from tinycua.config.types import AgentKind
from tinycua.config.agents import AgentConfigBase
from tinycua.agents.base import BaseAgentOrchestrator


def create_orchestrator(
    kind: AgentKind,
    config: AgentConfigBase | None = None,
) -> BaseAgentOrchestrator:
    """Create one orchestrator from its config.

    If config is None, uses the default config for the given AgentKind.
    Returns the typed orchestrator (e.g., QueryAnalyst).
    """


def create_all_orchestrators(
    config_overrides: dict[AgentKind, AgentConfigBase] | None = None,
) -> dict[AgentKind, BaseAgentOrchestrator]:
    """Create all seven internal orchestrators.

    config_overrides allows per-agent customization (extra tools, model, etc.)
    without modifying the default configs or orchestrator code.
    """
```

---

## Usage

```python
from tinycua.agents.factory import create_orchestrator, create_all_orchestrators
from tinycua.config.types import AgentKind
from tinycua.config.agents import QueryAnalystConfig

# Create with defaults
analyst = create_orchestrator(AgentKind.QUERY_ANALYST)
# analyst has config and empty state; no Agent created yet

# Create with overrides
custom_analyst = create_orchestrator(
    AgentKind.QUERY_ANALYST,
    config=QueryAnalystConfig(
        model=custom_model,
        extra_tools=[logging_tool, monitoring_tool],
    ),
)

# Create all for TinyCUA
orchestrators = create_all_orchestrators()
assert len(orchestrators) == 7  # 7 internal orchestrators
assert AgentKind.QUERY_ANALYST in orchestrators
```

---

## Internal Flow

```
create_orchestrator(AgentKind.QUERY_ANALYST, config)
  → Look up or use provided QueryAnalystConfig
  → Construct QueryAnalyst(config)
      → self.config = config
      → self.state = QueryAnalystState()
  → Return orchestrator instance
  (No SDK Agent created — that happens in run())
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Factory returns orchestrator, not Agent | `BaseAgentOrchestrator` subclass | Callers interact through `run()`, never directly with SDK Agent |
| `config=None` uses defaults | Default config per agent kind | Simple creation path; overrides only when needed |
| No Agent in factory | Agent built per-call in `run()` | Loop receives fresh state reference each invocation |
| Excludes TinyCUA | Internal orchestrators only | TinyCUA is the top-level composer, created separately |
