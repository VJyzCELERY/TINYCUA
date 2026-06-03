# Compaction

> **Status:** Target architecture

Compaction is session-level behavior configured through `SessionConfig`.

```text
SessionConfig
  · compaction_strategy
```

TinyCUA has root and per-node sessions. Compaction should apply to the session whose
`session_context` is being mutated. `chat_history` remains an audit trail and should not
be destructively compacted.

## Related

- [`../config/session_config.md`](../config/session_config.md)
- [`../models/session.md`](../models/session.md)
