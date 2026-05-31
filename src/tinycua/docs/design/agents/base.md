# BaseAgentOrchestrator

> **File:** `docs/design/agents/base.md`
> **Package:** `tinycua.agents.base`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`BaseAgentOrchestrator[S]` is the abstract generic base for all TinyCUA agent orchestrators.
It owns persistent configuration, typed runtime state, and a reference to its `Session`.
The SDK `Agent` is **not** persisted — it is constructed on-the-fly inside `run()` with
the loop receiving a direct reference to state.

---

## Class Contract

**File:** `tinycua/agents/base.py`

```python
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Generic, TypeVar

from tinycua.config.agents import AgentConfigBase
from tinycua.state.base import StateObject
from tinycua.state.session import Session

S = TypeVar("S", bound=StateObject)


class BaseAgentOrchestrator(ABC, Generic[S]):
    """Abstract base for all TinyCUA agent orchestrators.

    Owns persistent config, typed state, and a reference to its Session.
    Builds SDK Agent per-call by wiring state into the constructor of the
    custom loop.
    """

    config: AgentConfigBase
    state: S  # set by subclass — typed per-agent StateObject
    session: Session  # always set — auto-created as root if not provided

    def __init__(
        self,
        config: AgentConfigBase,
        session: Session | None = None,
    ):
        """Initialize the orchestrator.

        If session is None, a new root session is auto-created — the
        orchestrator can run standalone (useful for testing individual
        agents). When spawning a child, the parent links the child's
        auto-created session into the tree via self.session.add_child().
        """
        self.config = config
        if session is None:
            self.session = Session(
                session_id=str(uuid4()),
                agent_state=self.state,
            )
        else:
            self.session = session

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> AsyncIterator[dict]:
        """Domain-specific execution. Each orchestrator defines its own signature.

        Returns an async iterator yielding SDK stream events transparently.
        State is accumulated during iteration and stored at stream end.
        """

    # ── Instruction construction ──────────────────────────────────────

    def build_instruction(self, context: dict[str, Any]) -> str:
        """Build the complete system prompt: base instruction + dynamic context.

        The static instruction constant (self.config.instructions) provides
        the agent's role, input contract, output schema, and guardrails.

        context is a dict of named sections with defined priority order.
        Each key maps to a known context source. Missing keys and None
        values are silently skipped — the dict can carry whatever is
        available at call time:

            context = {
                "session":        Session,     # session metadata (NOT session_context)
                "project_files":  str,         # AGENTS.md / rules
                "agent_output":   dict,        # upstream agent result
            }

        Priority is defined in _build_context_section(). Subclasses may
        override the per-key formatters without touching assembly logic.

        Override points (any method, not just formatters):
          - build_instruction() — change entire assembly strategy
          - _build_context_section() — change key set or priority ordering
          - _format_session() — custom session metadata injection
          - _format_project_files() — custom project context injection
          - _format_agent_output() — custom upstream agent output formatting
        """
        sections = [self.config.instructions]
        context_section = self._build_context_section(context)
        if context_section:
            sections.append(context_section)
        return "\n\n".join(sections)

    def _build_context_section(self, context: dict[str, Any]) -> str | None:
        """Build the dynamic context block from the context dict.

        Processes known keys in priority order. Each key maps to a private
        formatter method. Missing/None values are silently skipped.
        Returns None if no context is available.
        """
        formatters = {
            "session": self._format_session,
            "project_files": self._format_project_files,
            "agent_output": self._format_agent_output,
        }
        parts: list[str] = []
        for key, formatter in formatters.items():
            value = context.get(key)
            if value is not None:
                formatted = formatter(value)
                if formatted:
                    parts.append(formatted)
        return "\n\n".join(parts) if parts else None

    def _format_session(self, session) -> str:
        """Format session metadata for the system prompt.
        Distinct from session.session_context (the message list passed as
        Agent.messages). This injects metadata like session_id, active
        phase, and current task into the system prompt.
        """
        ...

    def _format_project_files(self, content: str) -> str:
        """Format project-level files (AGENTS.md etc.)."""
        ...

    def _format_agent_output(self, output: dict) -> str:
        """Format upstream agent output for downstream consumption."""
        ...

    # ── Persistence ───────────────────────────────────────────────────

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
| State | `self.state` — agent-specific `StateObject` (NOT SDK `Agent.metadata`) |
| Session | `self.session` — own session node in the tree; child agents spawned via `self.session.add_child()` |
| Identity | Orchestrator class name + `self.config.name` |
| Base instruction | `self.config.instructions` — static constant (role, schema, guardrails) |
| Full instruction | `self.build_instruction(**context)` — base + dynamic session/project context |
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
| State read/write | `self.state` — direct reference to orchestrator's `StateObject` |
| Iteration logic | ReAct loop, gap evaluation, classification flow |

---

## Per-Call Agent Construction

Each orchestrator's `run()` builds a fresh SDK `Agent` with state wired into the loop.
The shape is identical across all orchestrators — only the names differ:

```python
class SomeOrchestrator(BaseAgentOrchestrator[SomeState]):
    config: SomeConfig
    state: SomeState

    async def run(self, domain_input: DomainType) -> AsyncIterator[dict]:
        # 1. Build instruction from base constant + dynamic context
        instructions = self.build_instruction({
            "session": self.session,
            "project_files": self.config.project_files,
        })

        # 2. Build query from domain input
        query = json.dumps({"domain_field": domain_input})

        # 3. Build SDK Agent per-call — no self.agent, no _build_agent()
        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=[*BASENAME_BASE_TOOLS, *self.config.extra_tools],
            loop=SomeLoop(state=self.state),
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
        self.state.domain_field = DomainType(**result)
        self.state.last_result = result
```

See individual orchestrator docs for concrete examples:
[`query_analyst.md`](query_analyst.md), [`information_digester.md`](information_digester.md), etc.

**Key points:**
- No `self.agent` — Agent is a local variable, rebuilt each call
- No `_build_agent()` — construction is in `run()`
- Instructions built via `self.build_instruction()` — static constant + dynamic context
- `stream=True` always — all events pass through to caller
- Text accumulated as a side-effect during passthrough
- After stream ends: JSON parse → typed state update

---

## State Injection Pattern

The loop constructor receives state by direct reference:

```python
loop = SomeLoop(state=self.state, extra_param=value)
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
# Standalone (testing): no session passed, orchestrator auto-creates a root session
analyst = QueryAnalyst(config)
async for event in analyst.run(user_query=...):
    pass
result = analyst.state.last_result

# Child spawning: parent links child's auto-created session into the tree
child = QueryAnalyst(config)  # child auto-creates its own session
self.session.add_child(child.session)
async for event in child.run(user_query=...):
    pass
result = child.state.last_result

# When child is done:
self.session.terminate_child(child.session)
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent built per-call | `Agent(...)` in `run()` | State injected fresh into loop each call; no stale Agent references |
| No persisted Agent | Local variable in `run()` | Agent is configuration, not state. Loop + tools define behavior |
| State as `self.state` | Typed `StateObject` subclass | Auto-completing, self-documenting; survives across calls |
| State injection into loop | `Loop(state=self.state, ...)` | Direct reference — loop reads/writes without LLM involvement |
| Generic typing | `BaseAgentOrchestrator[S]` | `self.state.mode_decision` works with autocomplete |
| Always `stream=True` | All `Agent.run()` calls stream | Real-time token access; transparent passthrough |
| Async generator return | `yield` events, store result in state | Caller sees streaming events; final state accessible after `async for` |
| `build_instruction(context: dict)` | Dict with priority-ordered keys, skip None | Standard format; handles missing context gracefully; no kwargs explosion |
| `session` owned by orchestrator | `self.session: Session \| None` | Every orchestrator holds its session node; child agents spawned via `self.session.add_child()` |


---


---


---

## See also

Prev : [Continuation State Store](../state/state_store.md) | Next : [Orchestrator Factory](factory.md)


## Related

- [self.session — auto-created if None](../state/session.md)
- [AgentState on self.session](../state/agent_state.md)
- [self.config — typed per-agent config](../config/agents.md)
- [Loops receive self.state by reference](../loops/overview.md)
