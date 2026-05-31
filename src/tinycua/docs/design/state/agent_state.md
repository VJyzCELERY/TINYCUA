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

Stored in our design `Session` as `states["agent"]: AgentState`.

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
```

`AgentStatus = Literal["idle", "running", "blocked", "terminated"]`

---

## Usage

```python
# During execution:
agent_state.status = "running"
agent_state.active_agent = "task_executor"
agent_state.active_task_id = "T-0.1"

# On session resume:
if agent_state.status == "running":
    orchestrator = internal_orchestrators[AgentKind(agent_state.active_agent)]
    async for event in orchestrator.run(task=load_task(agent_state.active_task_id)):
        yield event
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Flat lifecycle tracking | Status enum + active fields | Simple state machine; no complex resume logic |
| Consecutive failure count | `consecutive_failures: int` | Monitors for escalation without requiring external counters |
| Stored in Session.states | `states["agent"]` | Session is the serialization hub; all state lives there |


---

## See also

Prev : [Per-Agent State Classes](information.md) | Next : [`Task` Tree + `TaskResult`](task.md)
