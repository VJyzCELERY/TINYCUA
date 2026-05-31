# TinyCUA External Agent

> **File:** `docs/design/tinycua-agent.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft (contract only — implementation deferred to M6)
> **See also:** [`overview.md`](overview.md), [`loop-strategies.md`](loop-strategies.md), [`base-agent-wrapper.md`](base-agent-wrapper.md), [`agent-calls.md`](agent-calls.md)

---

## Role

The `TinyCUA` wrapper class is the single external entry point for the TINYCUA runtime.
It composes an SDK `Agent` with `MainLoop` and holds references to all internal agent
wrappers. Users interact with `tinycua.run(...)`, not with individual internal agents.

---

## Wrapper Class (Future M6)

**File:** `tinycua/agents/tinycua_agent.py`

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.factory import create_all_agents
from tinycua.config.tinycua import TinyCUAConfig
from tinycua.loops.main_loop import MainLoop


class TinyCUA:
    """External TinyCUA agent — wraps SDK Agent with MainLoop orchestration."""

    def __init__(self, config: TinyCUAConfig):
        self.config = config
        self.agent = Agent(
            name="tinycua",
            instructions=config.instructions,
            llm_model=config.model,
            loop=MainLoop(),
        )
        # Internal agent wrappers — typed, not hidden in SDK Agent.metadata
        self.internal_agents = create_all_agents(config.internal_agent_overrides)
        self.state_store = config.state_store
        self.artifact_store = config.artifact_store
        self.session_state: dict | None = None

        # Wire agent-calling tools into MainLoop's composed agent
        self._wire_agent_tools()

    async def run(self, user_query: str, session_id: str | None = None) -> Response:
        """Orchestrate the full TinyCUA flow."""
        ...

    def save_state(self, store) -> None:
        """Save current orchestration state."""
        ...

    def restore_state(self, store) -> None:
        """Restore orchestration state and resume."""
        ...
```

---

## Config

**File:** `tinycua/config/tinycua.py`

```python
@dataclass
class OrchestrationSettings:
    resume_enabled: bool = True
    checkpoint_after_each_phase: bool = True


@dataclass
class TinyCUAConfig:
    instructions: str = TINYCUA_MAIN_PROMPT
    model: LanguageModel = TINYCUA_DEFAULT_MODEL
    state_store: Any = None         # e.g., SQLiteMainLoopStateStore
    artifact_store: Any = None      # e.g., FileSystemArtifactStore
    internal_agent_overrides: dict[AgentKind, AgentConfigBase] = field(default_factory=dict)
    orchestration: OrchestrationSettings = field(default_factory=OrchestrationSettings)
```

---

## Instance Attributes (NOT `Agent.metadata`)

| Attribute | Type | Purpose |
|-----------|------|---------|
| `self.internal_agents` | `dict[AgentKind, BaseAgentWrapper]` | All seven configured wrapper instances |
| `self.state_store` | `Any \| None` | Structured session/continuation state store |
| `self.artifact_store` | `Any \| None` | Filesystem-backed storage for artifacts, snapshots, logs |
| `self.session_state` | `dict \| None` | Current session continuation state |

These are typed wrapper instance attributes — never buried in SDK `Agent.metadata`.

---

## MainLoop (future M6)

**File:** `tinycua/loops/main_loop.py`

`MainLoop` extends SDK `BaseLoop` and implements the full orchestration flow:

```
Query Analyst → ModeDecision
├── primary_agent → PrimaryAgent → response
├── worker → InformationDigester + Worker orchestration → PrimaryAgent → response
└── uncertain → escalate_user or explore
```

M2 defines the contract and `TinyCUA` wrapper shape. Implementation deferred to the
top-level orchestration milestone after session and worker orchestration foundations exist.

---

## Continuation State

`MainLoop` needs per-session continuation state so an interrupted run can resume.
The future state object should track:

- `session_id`
- Current orchestration phase (`query_analysis`, `primary_agent`, `information_digestion`, `worker`, `uncertain`, `final_response`)
- Active internal agent
- Active sub-session / Worker state reference
- Last completed step / checkpoint
- Pending user action
- Current `ContextEnhancedQuery`, `ModeDecision`, `DigestedInformation`
- Active `Task` tree and current task id
- Current `WorkerResult`
- Final response status

---

## Storage Preference

SQLite-first for structured session state. Optional filesystem-backed storage for
artifacts, snapshots, logs, and attachments. In-memory storage for tests and cache.

Each wrapper class's `save_state(store)` / `restore_state(store)` hooks accept a
storage backend parameter, leaving a clear contract for future persistence.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| One external entry point | `TinyCUA(...).run(...)` | Internal agents remain implementation details |
| State on wrapper, not metadata | Instance attributes | Typed, traceable, not obscured by SDK internals |
| Internal agent config overrides | `TinyCUAConfig.internal_agent_overrides` | MainLoop can customize agent behavior without code changes |
| MainLoop deferred | Contract only in M2 | Depends on session and worker orchestration foundations |
