# TinyCUA External Wrapper

> **File:** `docs/design/agents/tinycua.md`
> **Package:** `tinycua.agents.tinycua`

---

## Role

`TinyCUA` is the single external entry point. It composes an SDK `Agent` with `MainLoop`,
holds all internal agent wrappers, and manages session continuation state. Users interact
with `tinycua.run(...)` — internal agents are implementation details.

---

## Wrapper Class

**File:** `tinycua/agents/tinycua.py`

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.factory import create_all_agents
from tinycua.config.agents import TinyCUAConfig
from tinycua.loops.main_loop import MainLoop
from tinycua.tools.agent_calls import (
    call_query_analyst, call_information_digester,
    call_task_analyzer, call_task_assessor,
    call_task_executor, call_result_reviewer,
    call_primary_agent,
)


class TinyCUA:
    """External TinyCUA wrapper — composes SDK Agent with MainLoop."""

    def __init__(self, config: TinyCUAConfig):
        self.config = config
        self.internal_agents = create_all_agents(config.internal_agent_overrides)
        self.state_store = config.state_store
        self.artifact_store = config.artifact_store
        self.session_state: dict | None = None
        self.agent = self._build_agent()

    def _build_agent(self) -> Agent:
        return Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=self._build_agent_tools(),
            loop=MainLoop(),
        )

    def _build_agent_tools(self) -> list[Tool]:
        return [
            call_query_analyst(self.internal_agents),
            call_information_digester(self.internal_agents),
            call_task_analyzer(self.internal_agents),
            call_task_assessor(self.internal_agents),
            call_task_executor(self.internal_agents),
            call_result_reviewer(self.internal_agents),
            call_primary_agent(self.internal_agents),
        ]

    async def run(self, user_query: str, session_id: str | None = None) -> Response:
        if session_id:
            await self._restore_state(session_id)
        response = await self.agent.run(query=user_query)
        if self.config.orchestration.checkpoint_after_each_phase:
            await self._checkpoint(session_id)
        return response

    async def _restore_state(self, session_id: str):
        state = await self.state_store.load(session_id, "main_loop_state")
        if state:
            self.session_state = state

    async def _checkpoint(self, session_id: str):
        if session_id and self.state_store:
            await self.state_store.save(session_id, "main_loop_state", self.session_state)

    def save_state(self, store) -> None:
        """Save wrapper state and all internal agent states."""

    def restore_state(self, store) -> None:
        """Restore wrapper state and all internal agent states."""
```

---

## Config

`TinyCUAConfig` — `instructions=TINYCUA_MAIN_PROMPT`, `state_store`, `artifact_store`, `internal_agent_overrides`, `orchestration`.
See [`config/agents.md`](../config/agents.md#tinycuaconfig).

---

## Instance Attributes (NOT `Agent.metadata`)

| Attribute | Type | Purpose |
|-----------|------|---------|
| `self.internal_agents` | `dict[AgentKind, BaseAgentWrapper]` | All configured wrapper instances |
| `self.state_store` | `StateStore | None` | Structured session/continuation state |
| `self.artifact_store` | `Any | None` | Filesystem-backed storage for artifacts |
| `self.session_state` | `dict | None` | Current session continuation state |

---

## Agent-Calling Tools

TinyCUA's composed SDK `Agent` has all seven `call_*` tools available. `MainLoop` orchestrates
by invoking these tools, which delegate to the corresponding internal wrapper's `run()` method.

```python
# Inside MainLoop, the LLM can call:
#   call_query_analyst(user_query="...")
#   call_information_digester(context_enhanced_query={...})
#   call_task_analyzer(digested_information={...})
#   etc.
```

Each tool receives the wrapper instance, calls `wrapper.run(...)`, validates the output,
and returns the normalized result. The composed SDK `Agent` never sees raw SDK `Agent`
instances — only typed wrapper `run()` calls.

---

## State Store Integration

Default: `SQLiteStateStore(db_path="tinycua.db")`.

```python
tinycua = TinyCUA(
    TinyCUAConfig(
        state_store=SQLiteStateStore(db_path="tinycua.db"),
        artifact_store=FileSystemArtifactStore(base_dir="./tinycua_artifacts"),
    )
)
response = await tinycua.run("Research quantum computing", session_id="session-123")
# State is checkpointed after each orchestration phase
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| One external entry point | `TinyCUA(...).run(...)` | Internal agents remain implementation details |
| State on wrapper, not metadata | Instance attributes | Typed, traceable; not obscured by SDK internals |
| Agent-calling tools as delegation | `call_*` SDK Tools on composed agent | MainLoop invokes via natural language + tool calls |
| SQLite-first persistence | `SQLiteStateStore` as default | Durable, transactional, zero-config |
