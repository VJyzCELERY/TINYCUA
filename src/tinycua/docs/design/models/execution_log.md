# Execution Log

> **Package:** `tinycua.models.execution_log`
> **Status:** Target architecture

## Role

Execution logs capture node execution, tool use, retries, propagation, queue mutation,
and stream events.

```text
ExecutionLog
  · records: list[ExecutionLogRecord]

ExecutionLogRecord
  · record_id: str
  · event_type: str
  · source_node: str | None
  · source_node_id: str | None
  · source_session_id: str | None
  · attempt_number: int | None
  · payload: dict
  · created_at: datetime | str
  · metadata: dict
```

Log records include source node metadata where possible so queue, retry, propagation,
tool, and stream events can be traced back to their originating node/session.

## Related

- [`chat_record.md`](chat_record.md)
- [`../loops/tinycua_loop.md`](../loops/tinycua_loop.md)
