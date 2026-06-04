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
  · session_context: list[dict]
  · agent_state: AgentState | None
  · task: Task | None               # global parent session overall goal
  · todo: Todo | None                # per-session linear plan-then-execute list
```

Each node manages its own session/message context. A node session may be fresh,
inherited, reused, scoped from parent/root, or enhanced through retrieval tools.

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
chat_history    = audit trail with source node metadata
session_context = selected, deduped LLM-reusable messages
```

## Propagation

Propagation is controlled by `PropagationRule`; see [`../loops/propagation.md`](../loops/propagation.md).

## Compaction

Session compaction is selected by `session_config.compaction_strategy`. The strategy
takes `messages: list[dict]` and returns one assistant-role summary message. The strategy
may own its own internal Agent; this is not normal TinyCUALoop node execution.

Nodes invoke compaction with `session.compact_context()` when SessionConfig context limits
are exceeded. The session delegates to the configured strategy and replaces the selected
`session_context` window with the returned assistant summary. The node that requested
compaction builds any continuation prompt after compaction.

The default/simple strategy may be `SimpleCompaction`, which inherits parent Agent
configuration when available, uses a fallback config otherwise, runs a tool-less
compaction Agent over selected session messages, and stores that final response as:

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
