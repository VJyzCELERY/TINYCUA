# BaseAgentOrchestrator

> **File:** `docs/design/agents/base.md`
> **Package:** `tinycua.agents.base`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`BaseAgentOrchestrator[S]` is the abstract generic base for all TinyCUA agent orchestrators.
It owns persistent configuration and typed runtime state. The SDK `Agent` is **not** persisted —
it is constructed on-the-fly inside `run()` with the loop receiving a direct reference to state.

---

## Class Contract

**File:** `tinycua/agents/base.py`

```python
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Generic, TypeVar

from tinycua.config.agents import AgentConfigBase
from tinycua.state.information import StateInformation

S = TypeVar("S", bound=StateInformation)


class BaseAgentOrchestrator(ABC, Generic[S]):
    """Abstract base for all TinyCUA agent orchestrators.

    Owns persistent config and typed state. Builds SDK Agent per-call
    by wiring state into the constructor of the custom loop.
    """

    def __init__(self, config: AgentConfigBase):
        self.config: AgentConfigBase = config
        self.state: S  # set by subclass — typed per-agent StateInformation

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> AsyncIterator[dict]:
        """Domain-specific execution. Each orchestrator defines its own signature.

        Returns an async iterator yielding SDK stream events transparently.
        State is accumulated during iteration and stored at stream end.
        """

    def save_state(self, store: Any) -> None:
        """Save self.state to a storage backend. No-op default."""

    def restore_state(self, store: Any) -> None:
        """Restore self.state from a storage backend. No-op default."""
```

---

## Layer Separation

### Orchestrator Owns

| Concern | Location |
|---------|----------|
| Config | `self.config` — typed per-agent config dataclass |
| State | `self.state` — agent-specific `StateInformation` (NOT SDK `Agent.metadata`) |
| Identity | Orchestrator class name + `self.config.name` |
| Pre-processing | `run()` — builds query string from domain objects |
| Post-processing | `run()` — after stream ends: parse JSON, store state |
| Persistence | `save_state()` / `restore_state()` |
| Agent construction | `run()` — builds SDK `Agent` per-call with state injected into loop |

### SDK Agent Handles (per call)

| Concern | Location |
|---------|----------|
| LLM orchestration | `agent.run(query=..., stream=True)` |
| Tool execution | SDK handles calling, streaming, cancellation |
| Loop strategy | Configured via `loop=CustomLoop(state=self.state, ...)` in `Agent(...)` |

### Custom Loop Handles

| Concern | Location |
|---------|----------|
| Execution strategy | Override `run()` — define control flow, termination conditions |
| State read/write | `self.state` — direct reference to orchestrator's `StateInformation` |
| Iteration logic | ReAct loop, gap evaluation, classification flow |

---

## Per-Call Agent Construction

Each orchestrator's `run()` builds a fresh SDK `Agent` with state wired into the loop:

```python
class QueryAnalyst(BaseAgentOrchestrator[QueryAnalystState]):
    config: QueryAnalystConfig
    state: QueryAnalystState

    async def run(self, user_query: str, ...) -> AsyncIterator[dict]:
        agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*QUERY_ANALYST_BASE_TOOLS, *self.config.extra_tools],
            loop=QueryAnalystLoop(state=self.state),
        )
        input_msg = json.dumps({...})
        text_parts: list[str] = []
        async for event in agent.run(query=input_msg, stream=True):
            if event["type"] == "response.output_text.delta":
                text_parts.append(event["delta"])
            yield event
        raw = "".join(text_parts)
        result = json.loads(raw)
        self.state.mode_decision = ModeDecision(**result.get("mode_decision", {}))
        self.state.last_result = result
```

**Key points:**
- No `self.agent` — Agent is a local variable, rebuilt each call
- No `_build_agent()` — construction is in `run()`
- `stream=True` always — all events pass through to caller
- Text accumulated as a side-effect during passthrough
- After stream ends: JSON parse → typed state update

---

## State Injection Pattern

The loop constructor receives state by direct reference:

```python
loop = QueryAnalystLoop(state=self.state, session_context=session_context)
agent = Agent(..., loop=loop)
```

The loop reads/writes state during execution. Since it's a reference, any changes
are immediately visible to the orchestrator — even if the stream is interrupted mid-way.

---

## Return Convention

`run()` is an `async def` that **yields** events (async generator). The final result is
not returned — it is stored in `self.state.last_result`. Callers consume the stream with
`async for`, then access state:

```python
# Caller (e.g., agent-calling tool):
async for event in orchestrator.run(user_query=...):
    pass  # or log, forward, display
result = orchestrator.state.last_result
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent built per-call | `Agent(...)` in `run()` | State injected fresh into loop each call; no stale Agent references |
| No persisted Agent | Local variable in `run()` | Agent is configuration, not state. Loop + tools define behavior |
| State as `self.state` | Typed `StateInformation` subclass | Auto-completing, self-documenting; survives across calls |
| State injection into loop | `Loop(state=self.state, ...)` | Direct reference — loop reads/writes without LLM involvement |
| Generic typing | `BaseAgentOrchestrator[S]` | `self.state.mode_decision` works with autocomplete |
| Always `stream=True` | All `Agent.run()` calls stream | Real-time token access; transparent passthrough |
| Async generator return | `yield` events, store result in state | Caller sees streaming events; final state accessible after `async for` |
