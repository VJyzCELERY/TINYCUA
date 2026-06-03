# SessionConfig

> **Package:** `tinycua.config.session_config`
> **Status:** Target architecture

## Role

`SessionConfig` stores session-level behavior such as compaction. It is separate from
outer SDK `Agent` config and node-specific config.

```text
SessionConfig
  · compaction_strategy
  · metadata: dict
```

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
