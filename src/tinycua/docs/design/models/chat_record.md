# ChatRecord

> **Package:** `tinycua.models.chat_record`
> **Status:** Target architecture

## Role

`ChatRecord` is an append-only durable audit transcript of visible and internal events.
It records node I/O provenance, user/assistant messages, tool calls/results, retries,
monitor continuations, and queue lifecycle events. `ChatRecord` preserves chronological
provenance even when `session_context` compacts and loses prior messages.

`ChatRecord` is not the LLM memory itself. `session_context` entries may reference
durable `ChatRecord` entries by `chat_record_id` and provenance fields. LLM retry
continuations are recorded in `ChatRecord` when LLM-related or user/stream-visible,
even when they are not retained as reusable `session_context`.

Recommended metadata:

```text
ChatRecord
  · record_id: str
  · role: Literal["user", "assistant", "system", "tool"]
  · record_type: str
  · content: str | dict | list[dict]
  · visibility: Literal["user_visible", "internal", "tool_only"]
  · source_node_id: str | None
  - source_session_id: str | None
  · receiver_node_id: str | None
  · receiver_session_id: str | None
  · origin_record_id: str | None
  · created_seq: int
  · metadata: dict
```

`role` is the LLM/provider message role. `record_type` is the audit category, such as
`node_output`, `internal_continuation`, `tool_result`, `retry`, `queue_lifecycle`, or
`propagation` (appended when context crosses node/session boundaries during propagation).

`visibility` classifies the record for audit filtering:
- `user_visible`: Messages the end user can see (final responses, user queries).
- `internal`: Node-internal continuation or reasoning that is not user-facing but
  part of the audit trail.
- `tool_only`: Tool calls/results that are internal to execution.

`origin_record_id` supports dedupe when context is propagated or passed as node input. A
new record starts with `origin_record_id=None`; copied or propagated records preserve the
source record's `record_id` in `origin_record_id`. Dedupe compares `origin_record_id` when
present and falls back to `record_id`.

`receiver_node_id` and `receiver_session_id` track the intended consumer when a record
is forwarded as input to a downstream node.

## Relationship to Session Context

`session_context` is mutable and can compact/lose prior messages. `ChatRecord` is
append-only and preserves provenance. Session context entries may carry
`chat_record_id` references back to durable `ChatRecord` entries for traceability.

## Related

- [`session.md`](session.md)
- [`../loops/propagation.md`](../loops/propagation.md)
