# SessionConfig

> **Package:** `tinycua.config.session_config`
> **Status:** Target architecture

## Role

`SessionConfig` stores session-level behavior such as which compaction strategy to use.
It is separate from outer SDK `Agent` config and node-specific config.

```text
SessionConfig
  · compaction_strategy: CompactionStrategy | None
  · max_context_messages: int | None
  · max_context_tokens: int | None
  · metadata: dict
```

`SessionConfig` selects the strategy; it does not own all compaction behavior. The
`CompactionStrategy` class owns its own implementation/configuration and may internally
use an Agent. Compaction accepts `messages: list[dict]` and returns one assistant-role
summary message.

Nodes trigger compaction through `session.compact_context()` when
`max_context_messages` or `max_context_tokens` would be exceeded. The session chooses the
message window to compact according to session policy, delegates summary creation to the
configured strategy, and updates `session_context` with the returned assistant summary.
`chat_history` is not destructively compacted.

If no strategy is configured, future implementation may use `SimpleCompaction` as the
default simple strategy. `create_tinycua_agent(...)` or session setup initializes
`SimpleCompaction` with a parent SDK Agent configuration snapshot when available. It falls
back to documented defaults, runs a tool-less compaction Agent, and returns
`{"role": "assistant", "content": response}`.

## Factory Interaction

Future implementation should support:

```text
create_tinycua_agent(session=None, session_config=None, **agent_kwargs)
```

If `session is None`, a new root session is created. If `session_config` is provided, it
overrides or updates the generated/provided session's config according to documented
rules.

When the selected compaction strategy is `SimpleCompaction`, factory/session setup passes
a copy of the parent SDK Agent's model/provider configuration into the strategy before the
session is used. The strategy does not need the live Agent object during
`compact(messages)`.

## Related

- [`../models/session.md`](../models/session.md)
- [`node_config.md`](node_config.md)
- [`../utility/compaction.md`](../utility/compaction.md)
