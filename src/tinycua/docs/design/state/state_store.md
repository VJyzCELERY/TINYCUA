# State Store

> **File:** `docs/design/state/state_store.md`
> **Package:** `tinycua.state.state_store`
> **Last Updated:** 2026-06-02
> **Status:** Draft

---

## Role

The `StateStore` is the persistence backend for TinyCUA's continuation state. The
entire session tree (root + all child sessions) is saved and loaded as one unit inside
a snapshot. No per-agent key fragments — the tree is self-contained.

Persistence stores durable state, not live runtime objects. AgentNodes, AgentGraphs,
SDK `Agent` instances, and runtime-only node/graph IDs are reconstructed when a
session is loaded.

---

## Contract

```text
StateSnapshot — durable continuation envelope
    · root_session: Session
    · graph_queue: GraphQueueState | None

StateStore (ABC) — abstract persistence backend for TinyCUA continuation state

    save(session_id: str, snapshot: StateSnapshot) → None (async, abstract)
        · Persist the entire session tree under session_id as snapshot.root_session
        · root_session.to_dict() serializes recursively — root + all children,
          agent_states, tasks, and chat histories are included
        · Persist snapshot.graph_queue metadata needed to reconstruct active/future nodes

    load(session_id: str) → StateSnapshot | None (async, abstract)
        · Restore the continuation snapshot for session_id
        · Returns None if no state exists for this session_id
        · Returned snapshot.root_session has _parent references re-established via set_parents()

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
        · snapshot → await state_store.load(session_id)
        · if snapshot exists:
            · session → snapshot.root_session
            · hydrate graph queue from snapshot.graph_queue
            · active_item → graph.queue[0]
            · active_node → graph.materialize(active_item)  # active item only
            · if active_node.session.agent_state.status == "running":
                · return → await self._resume(active_node)
    · else:
        · session → new Session(session_id=uuid4(), agent_state=AgentState(
          type="tinycua", status="running"))
    · session.append_user(user_query)
    · for each event in self._orchestrate(session): yield event
    · snapshot → StateSnapshot(root_session=session, graph_queue=graph.queue.to_state())
    · await state_store.save(session.session_id, snapshot)
```

When a loaded root session has queue metadata, TinyCUA hydrates queue descriptors and
materializes runtime wrappers lazily:

```text
hydrate_graph(root_session, graph_queue_state):
  · re-establish parent links with root_session.set_parents()
  · rebuild GraphQueue descriptors from graph_queue_state.items
  · do not materialize every queued AgentNode/subgraph immediately
  · for the active queue item, or any item explicitly resumed/inspected:
      - if item has session_id and session_policy="reuse", find that Session in the loaded tree
      - if item is an AgentNode → load_agent_node(session)
      - if item is an AgentGraph → construct graph with session=session
  · for each queue item with session_policy="lazy":
      - keep AgentKind / NodeFactory unresolved until it reaches queue[0]
```

Hydration should never treat runtime-only `node_id`, `graph_id`, or `item_id` as
durable identifiers. Those IDs are regenerated for the new process. Stable resume
identity comes from `session_id`, `AgentState.type`, `AgentKind`, graph kind, and the
serialized queue structure.

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
        · Serialization handled by saving the StateSnapshot
```

---

## Graph Queue Serialization

The session tree records ownership/history, while the graph queue records execution
position. To resume an active graph, the state store must persist enough queue shape to
rebuild active and future work:

```text
GraphQueueState
  · items: list[GraphQueueItemState]

GraphQueueItemState
  · node_kind: AgentKind | GraphKind | RouterKind
  · session_id: str | None        # present when an existing Session should be reused
  · input: str | None
  · terminal: bool
  · session_policy: "lazy" | "reuse"
```

Live objects are reconstructed from this metadata:

- `session_policy="reuse"` + `session_id` → keep a descriptor until activation; then
  attach the existing Session and call `load_agent_node(session)` or construct the
  subgraph with `session=session`
- `session_policy="lazy"` → keep only the factory/kind until the item reaches
  `queue[0]`
- runtime queue handles (`item_id`) are regenerated and are not serialized

This keeps persistence crash-safe without coupling saved state to Python object
identity.

The lazy-hydration requirement is important for performance: a long-running TinyCUA
session may contain many completed or queued child sessions. Resume should restore the
durable tree and queue position, then materialize only the active path unless callers
explicitly ask to inspect another node.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Snapshot as persistence unit | `save(session_id, snapshot)` saves session tree + queue metadata | Resume needs both durable ownership/history and execution position |
| SQLite-first | `SQLiteStateStore` as default | Durable, transactional, zero-config for single-machine deployments |
| Pluggable backends | `StateStore` ABC | In-memory for tests, filesystem for artifacts, SQLite for sessions |
| No per-agent keys | Removed `save(session_id, key, data)` → tree-based | Keys added unnecessary fragmentation; tree is always consistent |
| Recursive serialization | `StateObject.to_dict()` on root serializes tree | `dataclasses.asdict()` handles nested Session, Task, AgentState, etc. |
| Runtime wrappers reconstructed | Load Sessions, then rebuild AgentNodes/AgentGraphs | SDK Agents and node objects are not durable state |
| Queue metadata persisted | Store queue shape separately from child sessions | Resume needs active/future execution position, not just ownership history |
| Runtime IDs not persisted | Regenerate `node_id`, `graph_id`, and `item_id` | IDs are live-process handles; stable resume uses session/kind metadata |
| Lazy hydration | Materialize only active/inspected wrappers | Avoids slowing restore by rebuilding inactive branches |


---


---


---

## See also

Prev : [`ChatRecord` Audit Trail](chat_record.md) | Next : [`BaseAgentNode`](../agent_node/base.md)


## Related

- [Saves/loads entire Session tree](session.md)
