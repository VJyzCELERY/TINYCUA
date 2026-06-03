# Propagation

> **Package:** `tinycua.loops.propagation`
> **Status:** Target architecture

## Role

Propagation controls what crosses node/session boundaries. It preserves the useful old
`Session.terminate_child(...)` behavior while making it explicit and configurable.

```text
PropagationRule
  · chat_history: none | parent | root
  · session_context: none | parent | root
  · session_context_mode: none | final | full | selected
  · token_usage: none | parent | root
  · failure: none | parent | root
  · dedupe: bool
```

## Profiles

| Profile | chat_history | session_context | token_usage | failure |
|---------|--------------|-----------------|-------------|---------|
| transient_legacy | parent/root | none | parent/root | parent/root |
| natural_termination_legacy | parent/root | final | parent/root | parent/root |
| mid_progress_legacy | parent/root | full | parent/root | parent/root |
| selected_internal_output | root | selected | root | root |

## Chat History vs Session Context

```text
chat_history    = audit trail, including internal node messages and source metadata
session_context = selected, deduped LLM-reusable context
```

Node input messages are not automatically stored again. Nodes store new outputs and
selected reusable context only.

## Related

- [`node_queue.md`](node_queue.md)
- [`../models/session.md`](../models/session.md)
