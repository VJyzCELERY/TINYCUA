# State Store

> **File:** `docs/design/state/state_store.md`
> **Package:** `tinycua.state.state_store`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

The `StateStore` is the persistence backend for TinyCUA's session continuation state.
The entire session tree (root + all child sessions) is saved and loaded as one unit.
No per-agent key fragments — the tree is self-contained.

---

## Contract

```python
from abc import ABC, abstractmethod


class StateStore(ABC):
    """Abstract persistence backend for TinyCUA session state."""

    @abstractmethod
    async def save(self, session_id: str, session: "Session") -> None:
        """Persist the entire session tree under session_id.

        session.to_dict() serializes recursively — the root and all
        children, agent_states, tasks, and chat histories are included.
        """
        ...

    @abstractmethod
    async def load(self, session_id: str) -> "Session | None":
        """Restore the entire session tree for session_id.

        Returns None if no state exists for this session_id.
        The returned Session has _parent references re-established
        via set_parents().
        """
        ...

    @abstractmethod
    async def delete(self, session_id: str) -> None: ...

    @abstractmethod
    async def list_sessions(self) -> list[str]: ...
```

---

## Implementations

| Backend | Class | Use Case |
|---------|-------|----------|
| SQLite | `SQLiteStateStore` | Production — structured session state, transactional persistence |
| Filesystem | `FileSystemStateStore` | Artifacts, snapshots, logs, attachments, simple deployments |
| In-Memory | `MemoryStateStore` | Tests, development, cache |

---

## TinyCUA Integration

```python
class TinyCUA:
    def __init__(self, config: TinyCUAConfig):
        self.state_store = config.state_store  # SQLiteStateStore(db_path="tinycua.db")

    async def run(self, user_query: str, session_id: str | None = None) -> Response:
        # Restore or create session
        if session_id:
            session = await self.state_store.load(session_id)
            if session:
                # Resume from active point in the tree
                active = session.get_active_session()
                if active.agent_state and active.agent_state.status == "running":
                    return await self._resume(active)
        else:
            session = Session(
                session_id=str(uuid4()),
                agent_state=AgentState(active_agent="tinycua", status="running"),
            )

        # Run orchestration flow...
        session.append_user(user_query)
        async for event in self._orchestrate(session):
            yield event

        # Persist the entire tree
        await self.state_store.save(session.session_id, session)
```

---

## Agent-Level Serialization

Each orchestrator's state lives on its session's `agent_state`. Serialization is
handled by the session tree — no per-agent `save_state`/`restore_state` methods needed:

```python
class BaseAgentOrchestrator(Generic[S]):
    # The orchestrator mutates self.state during execution.
    # Before yielding events, it attaches self.state to the session:
    
    async def run(self, session: Session | None = None, **kwargs) -> AsyncGenerator:
        if session:
            session.agent_state = self.state
        # ... agent execution ...
        # After execution, self.state is already on session.agent_state
        # (same reference). Serialization is handled by the session tree.
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tree as unit of persistence | `save(session_id, session)` saves entire tree | Self-contained; children only exist within parent's scope |
| SQLite-first | `SQLiteStateStore` as default | Durable, transactional, zero-config for single-machine deployments |
| Pluggable backends | `StateStore` ABC | In-memory for tests, filesystem for artifacts, SQLite for sessions |
| No per-agent keys | Removed `save(session_id, key, data)` → tree-based | Keys added unnecessary fragmentation; tree is always consistent |
| Recursive serialization | `StateObject.to_dict()` on root serializes tree | `dataclasses.asdict()` handles nested Session, Task, AgentState, etc. |


---


---


---

## See also

Prev : [Design `Session`](session.md) | Next : [`BaseAgentOrchestrator[S]`](../agents/base.md)
