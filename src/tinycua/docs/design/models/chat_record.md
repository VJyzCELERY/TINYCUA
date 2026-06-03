# ChatRecord

> **Package:** `tinycua.models.chat_record`
> **Status:** Target architecture

## Role

`ChatRecord` is the audit-log record for user input, node output, internal continuation,
tool calls/results, retries, monitor continuations, and queue lifecycle events.

Recommended metadata:

```text
ChatRecord
  · record_id: str
  · role/type
  · content
  · source_node: str | None
  · source_node_id: str | None
  · source_session_id: str | None
  · origin_record_id: str | None
  · metadata: dict
```

`origin_record_id` supports dedupe when context is propagated or passed as node input.

## Related

- [`session.md`](session.md)
- [`../loops/propagation.md`](../loops/propagation.md)
