# BaseAgentWrapper

> **File:** `docs/design/agents/base.md`
> **Package:** `tinycua.agents.base`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`BaseAgentWrapper[S]` is the abstract generic base for all TinyCUA agent wrapper classes.
It composes (does not extend) an SDK `Agent` internally and manages a typed `StateInformation`
subclass. The composed SDK `Agent` is never publicly exposed — all interaction goes through
the wrapper's `run()` method.

---

## Class Contract

**File:** `tinycua/agents/base.py`

```python
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from tinycua_sdk.agent import Agent
from tinycua.config.agents import AgentConfigBase
from tinycua.state.information import StateInformation

S = TypeVar("S", bound=StateInformation)


class BaseAgentWrapper(ABC, Generic[S]):
    """Abstract base for all TinyCUA internal agent wrappers."""

    state: S

    def __init__(self, config: AgentConfigBase, state_factory: type[S]):
        self.config = config
        self.agent: Agent | None = None           # set by subclass _build_agent()
        self.state = state_factory()               # agent-specific StateInformation

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Domain-specific execution. Each wrapper defines its own input/output schema."""

    def save_state(self, store: Any) -> None:
        """Save self.state to a storage backend. No-op default."""

    def restore_state(self, store: Any) -> None:
        """Restore self.state from a storage backend. No-op default."""
```

---

## Layer Separation

### Wrapper Owns

| Concern | Location |
|---------|----------|
| Config | `self.config` — typed per-agent config dataclass |
| State | `self.state` — agent-specific `StateInformation` (NOT SDK `Agent.metadata`) |
| Identity | Wrapper class name + `self.config.name` |
| Pre-processing | `run()` — builds input messages from domain objects |
| Post-processing | `run()` — validates output, parses into M1 types, stores state |
| Persistence | `save_state()` / `restore_state()` |
| Logging/verbosity | Managed at wrapper level |

### Composed SDK Agent Owns

| Concern | Location |
|---------|----------|
| LLM orchestration | `self.agent.run()` |
| Tool execution | SDK handles calling, streaming, cancellation |
| Loop strategy | Configured via `loop=` in `_build_agent()` |

---

## Tool Sources Pattern

Every wrapper's `_build_agent()` merges exactly two tool sources:

```python
self.agent = Agent(
    ...
    tools=[*QUERY_ANALYST_BASE_TOOLS, *self.config.extra_tools],
    loop=QueryAnalystLoop(),
)
```

| Source | Location | Purpose |
|--------|----------|---------|
| `*_BASE_TOOLS` | `tinycua.constants.tools` | Pre-configured, code-level tool set |
| `config.extra_tools` | Agent config dataclass | Externally injected — **empty by default** |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Composition vs inheritance | Compose SDK Agent; do not extend | Keeps SDK Agent as internal detail; wrapper exposes typed API |
| State as `self.state`, not `Agent.metadata` | Typed `StateInformation` subclass | Auto-completing, self-documenting; not obscured by SDK internals |
| Generic typing | `BaseAgentWrapper[S]` | `self.state.mode_decision` works with autocomplete |
| Abstract `run()` | Each wrapper defines its own | Domain-specific input/output differ per agent |
| `save_state()` / `restore_state()` | Default no-op, accepts backend | Compatible with future persistence without forcing M2 implementation |
