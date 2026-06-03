# SessionConfig

> **Package:** `tinycua.config.session_config`
> **Status:** Target architecture

## Role

`SessionConfig` stores session-level behavior such as which compaction strategy to use.
It is separate from outer SDK `Agent` config and node-specific config.

```text
SessionConfig
  · compaction_strategy: CompactionStrategy | None
  · metadata: dict
```

`SessionConfig` selects the strategy; it does not own all compaction behavior. The
`CompactionStrategy` class owns its own implementation/configuration and may internally
use an Agent. Compaction accepts `messages: list[dict]` and returns one assistant-role
summary message.

If no strategy is configured, future implementation may use `SimpleCompaction` as the
default simple strategy. `SimpleCompaction` inherits parent Agent configuration where
available, falls back to documented defaults, runs a tool-less compaction Agent, and
returns `{"role": "assistant", "content": response}`.

## Factory Interaction

Future implementation should support:

```text
create_tinycua_agent(session=None, agent_config=None, session_config=None, ...)
```

If `session is None`, a new root session is created. If `session_config` is provided, it
overrides or updates the generated/provided session's config according to documented
rules.

## Related

- [`../models/session.md`](../models/session.md)
- [`node_config.md`](node_config.md)
- [`../utility/compaction.md`](../utility/compaction.md)
