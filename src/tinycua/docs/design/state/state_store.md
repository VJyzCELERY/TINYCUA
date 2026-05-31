# State Store

> **File:** `docs/design/state/state_store.md`
> **Package:** `tinycua.state.state_store`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

The `StateStore` is the persistence backend for TinyCUA's session continuation state.
The TinyCUA wrapper and each internal agent use it to checkpoint progress so an interrupted
run can resume from the last safe point.

---

## Contract

```python
from abc import ABC, abstractmethod
from typing import Any


class StateStore(ABC):
    """Abstract persistence backend for TinyCUA state."""

    @abstractmethod
    async def save(self, session_id: str, key: str, data: Any) -> None: ...

    @abstractmethod
    async def load(self, session_id: str, key: str) -> Any | None: ...

    @abstractmethod
    async def delete(self, session_id: str, key: str) -> None: ...

    @abstractmethod
    async def list_keys(self, session_id: str) -> list[str]: ...
```

---

## Implementations

| Backend | Class | Use Case |
|---------|-------|----------|
| SQLite | `SQLiteStateStore` | Production — structured session state, transactional checkpoints |
| Filesystem | `FileSystemStateStore` | Artifacts, snapshots, logs, attachments, simple deployments |
| In-Memory | `MemoryStateStore` | Tests, development, cache |

---

## TinyCUA Integration

```python
class TinyCUA:
    def __init__(self, config: TinyCUAConfig):
        self.state_store = config.state_store  # SQLiteStateStore(db_path="tinycua.db")

    async def run(self, user_query: str, session_id: str | None = None) -> Response:
        # Restore previous state if available
        if session_id:
            prev_state = await self.state_store.load(session_id, "main_loop_state")
            if prev_state:
                self._restore_orchestration(prev_state)

        # Run orchestration flow...

        # Checkpoint after each phase
        if self.config.orchestration.checkpoint_after_each_phase:
            await self.save_state(self.state_store, session_id)
```

---

## Agent-Level Persistence

Each wrapper's `save_state(store)` and `restore_state(store)` accept a `StateStore`
backend parameter:

```python
class BaseAgentWrapper(Generic[S]):
    def save_state(self, store: StateStore) -> None:
        """Serialize self.state to the store."""

    def restore_state(self, store: StateStore) -> None:
        """Hydrate self.state from the store."""
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| SQLite-first | `SQLiteStateStore` as default | Durable, transactional, zero-config for single-machine deployments |
| Pluggable backends | `StateStore` ABC | In-memory for tests, filesystem for artifacts, SQLite for sessions |
| Agent-level hooks | `save_state()` / `restore_state()` on wrapper | Each agent owns its state serialization |
| Checkpoint-after-phase | Configurable in `OrchestrationSettings` | Control granularity of persistence |
