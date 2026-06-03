# Execution Log

> **Package:** `tinycua.models.execution_log`
> **Status:** Target architecture

## Role

Execution logs capture node execution, tool use, retries, propagation, queue mutation,
and stream events.

Log records should include source node metadata where possible:

- node name
- node id
- session id
- attempt number
- event type

## Related

- [`chat_record.md`](chat_record.md)
- [`../loops/tinycua_loop.md`](../loops/tinycua_loop.md)
