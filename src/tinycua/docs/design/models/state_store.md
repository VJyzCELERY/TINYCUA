# State Store

> **Package:** `tinycua.models.state_store`
> **Status:** Target architecture note

## Role

State store docs describe persistence shape considerations for sessions and queue state.

Datastore persistence implementation is out of scope for the current architecture
roadmap draft, but the design should remain compatible with future persistence.

Stable persisted state should use session ids, task ids, and serialized queue metadata.
Runtime node ids may be regenerated.

## Related

- [`session.md`](session.md)
- [`../loops/node_queue.md`](../loops/node_queue.md)
