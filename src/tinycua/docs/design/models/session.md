# Session

> **Package:** `tinycua.models.session`
> **Status:** Target architecture

## Role

Sessions are state containers for root TinyCUA state and per-node message context.

```text
Session
  · session_id: str
  · parent_id: str | None
  · session_config: SessionConfig
  · chat_history: list[ChatRecord]
  · session_context: list[SessionContextEntry]
  · agent_state: AgentState | None
  · task: Task | None               # global parent session overall goal
  · todo: Todo | None                # per-session linear plan-then-execute list
  · compact_context(window: list[dict] | None = None) → dict | None
```

Each node manages its own session/message context. A node session may be fresh,
inherited, reused, scoped from parent, scoped from root, or enhanced through retrieval
tools.

## Task vs Todo

| Concept | Scope | Purpose |
|---------|-------|---------|
| `Task` | Global parent session | Overall goal of the entire session. The high-level "what needs to be done." |
| `Todo` | Per-session isolated | Small, linear, non-complex list for plan-then-execute. The low-level "how to get there now." |

`Task` is the parent session's single overall objective (e.g., "Implement user authentication").
`Todo` is a simple ordered list the current node can use to break its immediate work into
checkable steps (e.g., ["Read auth module", "Add login endpoint", "Write tests"]). Nodes
are not required to use Todo, but every session provides access to one.

## SDK Messages

SDK `Agent.run(..., messages=[...])` passes messages into `TinyCUALoop`. TinyCUA should
merge/record those messages according to session policy with dedupe. The SDK already
appends the current external user query to the message list.

## Messages

Only actual external user input is role `user`. Internal TinyCUA node communication is
assistant-role continuation. Tool messages may use provider-required tool roles.

```text
chat_history    = durable append-only audit transcript (ChatRecord)
session_context = mutable, selected, deduped LLM-reusable messages
```

`session_context` entries may carry `chat_record_id` / provenance fields referencing
durable `ChatRecord` entries. Normal LLM context propagation is separate from durable
audit recording — see [`chat_record.md`](chat_record.md).

## Segmented Context

Each node's session context is segmented for propagation control. Records carry
metadata so implementation does not rely on index slicing:

```text
SessionContextEntry (standalone dataclass — extends ChatRecord is a future refactoring target)
  · segment: Literal["prior", "input", "output"]
  · origin_record_id: str | None
  · source_node_id: str | None
  · source_session_id: str | None
  · created_seq: int
```

- **prior**: Inherited from parent propagation or previous nodes.
- **input**: Received as `NodeInput` when this node was entered.
- **output**: New records produced by this node's execution.

On node termination, `propagate_to_parent` excludes the `output_segment`; the
`output_segment` is forwarded to the next node as `NodeInput`. See
[`../loops/propagation.md`](../loops/propagation.md) for the full contract.

## Propagation

Propagation is controlled by `PropagationRule`; see [`../loops/propagation.md`](../loops/propagation.md).

## Compaction

Session compaction is selected by `session_config.compaction_strategy`. The strategy
takes `messages: list[dict]` and returns one assistant-role summary message. The strategy
may own its own internal Agent; this is not normal TinyCUALoop node execution.

Nodes invoke compaction with `session.compact_context(window=None)` when SessionConfig
context limits are exceeded. If `window` is omitted, the session selects a compactable
window from `session_context` according to policy. The method delegates to the configured
strategy, replaces the selected `session_context` window with the returned assistant
summary, and returns that summary. If no strategy is configured or no compaction is
needed, it returns `None`. The node that requested compaction builds any continuation
prompt after compaction.

The default/simple strategy may be `SimpleCompaction`, initialized by
`create_tinycua_agent(...)` or session setup with a parent SDK Agent configuration snapshot
when available. It uses a fallback config otherwise, runs a tool-less compaction Agent over
selected session messages, and stores that final response as:

```text
{"role": "assistant", "content": response}
```

System-role messages are excluded from compaction targets by default unless the caller
intentionally passes dynamic system context for summarization.

## Related

- [`state_object.md`](state_object.md)
- [`chat_record.md`](chat_record.md)
- [`todo.md`](todo.md)
- [`../utility/compaction.md`](../utility/compaction.md)
