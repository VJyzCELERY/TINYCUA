# Propagation

> **Package:** `tinycua.loops.propagation`
> **Status:** Target architecture

## Role

Propagation controls what crosses node/session boundaries. It preserves the useful old
`Session.terminate_child(...)` behavior while making it explicit and configurable.

```text
PropagationRule
  · chat_history: none | parent | root
  · session_context_target: none | parent | root | parent_and_root
  · session_context_mode: none | final | full | selected
  · token_usage: none | parent | root | parent_and_root
  · failure: none | parent | root | parent_and_root
  · dedupe: bool
```

## Profiles

| Profile | chat_history | session_context_target | session_context_mode | token_usage | failure |
|---------|--------------|------------------------|----------------------|-------------|---------|
| transient_legacy | parent_and_root | none | none | parent_and_root | parent_and_root |
| natural_termination_legacy | parent_and_root | parent_and_root | final | parent_and_root | parent_and_root |
| mid_progress_legacy | parent_and_root | parent_and_root | full | parent_and_root | parent_and_root |
| selected_internal_output | root | root | selected | root | root |

## Chat History vs Session Context

```text
chat_history    = audit trail, including internal node messages and source metadata
session_context = selected, deduped LLM-reusable context
```

Node input messages are not automatically stored again. Nodes store new outputs and
selected reusable context only.

## Dedupe

`ChatRecord.origin_record_id` is assigned when a record is copied, propagated, or reused
as input. New records use their own `record_id`; copied records preserve the original
record's id as `origin_record_id`.

Dedupe precedence:

1. `PropagationRule.dedupe` filters writes into parent, root, or parent-and-root
   `session_context` destinations during
   propagation.
2. `NodeMessagePolicy.dedupe_by_origin_record_id` filters the final LLM-bound node input
   before `build_messages()` returns.
3. Both compare `origin_record_id` when present, falling back to `record_id`.
4. When duplicates are found, keep the earliest existing record in the destination and
   skip later duplicates.

## Related

- [`node_queue.md`](node_queue.md)
- [`../models/session.md`](../models/session.md)
