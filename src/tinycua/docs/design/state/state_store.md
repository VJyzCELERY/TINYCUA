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

```text
StateStore (ABC) — abstract persistence backend for TinyCUA session state

    save(session_id: str, session: Session) → None (async, abstract)
        · Persist the entire session tree under session_id
        · session.to_dict() serializes recursively — root + all children,
          agent_states, tasks, and chat histories are included

    load(session_id: str) → Session | None (async, abstract)
        · Restore the entire session tree for session_id
        · Returns None if no state exists for this session_id
        · Returned Session has _parent references re-established via set_parents()

    delete(session_id: str) → None (async, abstract)

    list_sessions() → list[str] (async, abstract)
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

```text
TinyCUA.__init__(config: TinyCUAConfig)
    · self.state_store → config.state_store

TinyCUA.run(user_query: str, session_id: str | None = None) → Response (async)
    · if session_id is provided:
        · session → await state_store.load(session_id)
        · if session exists:
            · active → session.get_active_session()
            · if active.agent_state.status == "running":
                · return → await self._resume(active)
    · else:
        · session → new Session(session_id=uuid4(), agent_state=AgentState(
          type="tinycua", status="running"))
    · session.append_user(user_query)
    · for each event in self._orchestrate(session): yield event
    · await state_store.save(session.session_id, session)
```

---

## AgentNode-Level Serialization

Each agent's state lives on its session's `agent_state`. Serialization is handled by
the session tree — no per-agent `save_state`/`restore_state` methods needed:

```text
BaseAgentNode
    · Owns a session reference
    · Loops mutate session.agent_state during execution

    run(**kwargs) → AsyncGenerator (async)
        · Execute node logic
        · session.agent_state is already part of the session tree
        · Serialization handled by saving the root session
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

Prev : [`ChatRecord` Audit Trail](chat_record.md) | Next : [`BaseAgentNode`](../agent_node/base.md)


## Related

- [Saves/loads entire Session tree](session.md)
