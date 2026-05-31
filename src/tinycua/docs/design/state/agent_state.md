# Agent State

> **File:** `docs/design/state/agent_state.md`
> **Package:** `tinycua.state.agent_state`
> **Last Updated:** 2026-05-31

---

## Role

`AgentState` tracks internal agent lifecycle — which agent is active, which task
it's on, operational status, and failure tracking. Used for session continuity:
on resume, the system reads `active_agent` and `active_task_id` to route directly
to the right orchestrator.

Stored directly on `Session.agent_state` — each session node holds its own agent's
state. To find which agent is currently active, walk the session tree to the deepest
leaf via `session.get_active_session()`.

---

## Class Contract

**File:** `tinycua/state/agent_state.py`

```python
@dataclass
class AgentState(StateObject):
    active_agent: str                    # name of active agent
    active_task_id: str | None = None    # currently active task ID
    status: AgentStatus = "idle"         # idle | running | blocked | terminated
    resume_target: str | None = None     # resume target description
    consecutive_failures: int = 0        # non-negative

    # Session-level metadata (set on root session's AgentState)
    last_query: dict[str, Any] = field(default_factory=dict)
    last_result: dict[str, Any] = field(default_factory=dict)

    # Config reference for context window derivation
    agent_config: Any = None  # AgentConfigBase — provides model.context_window
```

`AgentStatus = Literal["idle", "running", "blocked", "terminated"]`

---

## Usage

```python
# During execution:
session.agent_state.status = "running"
session.agent_state.active_agent = "task_executor"
session.agent_state.active_task_id = "T-0.1"

# On session resume — walk the tree to find the active session:
active_session = root_session.get_active_session()
agent = active_session.agent_state
if agent and agent.status == "running":
    orchestrator = internal_orchestrators[AgentKind(agent.active_agent)]
    async for event in orchestrator.run(
        task=load_task(agent.active_task_id)
    ):
        yield event
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Flat lifecycle tracking | Status enum + active fields | Simple state machine; no complex resume logic |
| Consecutive failure count | `consecutive_failures: int` | Monitors for escalation without requiring external counters |
| Stored per session node | `Session.agent_state` on each session | Walk the tree to find who's active; no central dict needed |
| Resume via tree walk | `get_active_session()` → `agent_state` | Deepest leaf IS the active agent; no explicit routing key |
| Session metadata on root | `last_query`, `last_result` on root AgentState | Always reachable via `session.root()` |
| Config on AgentState | `agent_config: AgentConfigBase` | Provides context window for compaction checks per session |


---


---


---

## See also

Prev : [Per-Agent State Classes](information.md) | Next : [`Task` Tree + `TaskResult`](task.md)


## Related

- [Stored on Session.agent_state per node](session.md)
- [agent_config provides context window](../config/agents.md)
