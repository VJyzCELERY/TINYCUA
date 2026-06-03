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
  · task: Task | None
  · todo_list
```

Each node manages its own session/message context. A node session may be fresh,
inherited, reused, scoped from parent/root, or enhanced through retrieval tools.

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

## Related

- [`state_object.md`](state_object.md)
- [`chat_record.md`](chat_record.md)
