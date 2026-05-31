# BaseAgentWrapper

> **File:** `docs/design/base-agent-wrapper.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft
> **See also:** [`overview.md`](overview.md), [`loop-strategies.md`](loop-strategies.md), [`../architecture/state-objects.md`](../architecture/state-objects.md)

---

## Role

`BaseAgentWrapper` is the abstract base class for all TinyCUA internal agent wrappers.
It composes (does not extend) an SDK `Agent` internally and manages a typed `StateInformation` instance.
The composed SDK `Agent` is never publicly exposed — all interaction goes through the wrapper's `run()` method.

---

## Class Contract

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
        self.agent: Agent | None = None           # set by _build_agent()
        self.state = state_factory()               # agent-specific StateInformation

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Domain-specific execution. Subclasses override."""

    def save_state(self, store: Any) -> None:
        """Save wrapper state (self.state) to a storage backend. No-op default."""

    def restore_state(self, store: Any) -> None:
        """Restore wrapper state from a storage backend. No-op default."""
```

---

## StateInformation

`StateInformation` is an abstract base dataclass — each agent defines a concrete subclass
with fields specific to that agent's domain. This gives each agent typed, self-documenting
state instead of a raw dict.

```python
from abc import ABC
from dataclasses import dataclass, field
from tinycua.state import (
    ContextEnhancedQuery, ModeDecision,
    DigestedInformation, Task, TaskResult,
    ReviewerDecision, ReviewStatus,
)


@dataclass
class StateInformation(ABC):
    """Abstract base for per-agent structured runtime state."""
    session_id: str | None = None
    chat_history: list[dict] = field(default_factory=list)
    last_query: dict[str, Any] = field(default_factory=dict)
    last_result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

### Per-Agent Subclasses

| Subclass | Agent | Agent-Specific Fields |
|----------|-------|----------------------|
| `QueryAnalystState` | QueryAnalyst | `mode_decision: ModeDecision \| None`, `context_enhanced_query: ContextEnhancedQuery \| None`, `classification_score: float \| None` |
| `InformationDigesterState` | InformationDigester | `digested_information: DigestedInformation \| None`, `retrieval_iterations: int` |
| `TaskAnalyzerState` | TaskAnalyzer | `task_tree: Task \| None` |
| `TaskAssessorState` | TaskAssessor | `selected_task_ids: list[str]` |
| `TaskExecutorState` | TaskExecutor | `task_result: TaskResult \| None`, `execution_attempts: int`, `tool_results: list[dict]` |
| `ResultReviewerState` | ResultReviewer | `reviewer_decision: ReviewerDecision \| None`, `deterministic_failures: list[str]`, `last_review_status: ReviewStatus \| None` |
| `PrimaryAgentState` | PrimaryAgent | `final_response: dict`, `citations: list[str]` |

Full definitions in `tinycua/state/information.py`.

---

## Layer Separation

The wrapper owns everything that is NOT the execution loop strategy:

- **Config**: `self.config` — typed per-agent config dataclass
- **State**: `self.state` — agent-specific `StateInformation` subclass (NOT SDK `Agent.metadata`)
- **Identity**: The wrapper class name and `self.config.name`
- **Persistence**: `save_state()` / `restore_state()` accepting a storage backend
- **Logging/verbosity**: Managed at the wrapper level, not inside the loop

The composed SDK `Agent` owns:

- **LLM orchestration**: Delegated to `self.agent.run()`
- **Tool execution**: SDK handles tool calling, streaming, cancellation
- **Loop strategy**: `self.agent` is configured with the appropriate loop via `loop=`

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Composition vs inheritance | Compose SDK Agent; do not extend | Keeps SDK Agent as an internal detail; allows wrapper to expose its own typed API |
| State storage | `self.state: StateInformation` | Typed, self-documenting; never obscured by SDK's opaque `Agent.metadata` |
| Generic typing | `BaseAgentWrapper[S]` | Enables `self.state.mode_decision` with autocomplete, not `self.state["mode_decision"]` |
| Abstract `run()` | Each wrapper defines its own | Domain-specific input schema and output parsing differ per agent |
| `save_state()` / `restore_state()` | No-op default, accepts backend | Compatible with future SQLite/filesystem stores without forcing implementation in M2 |
