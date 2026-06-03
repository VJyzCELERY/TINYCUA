# Information Digestion Tools

> **Status:** Target architecture

`TinyCUAInformationDigesterNode` uses information-digestion tools to gather and summarize
context for downstream nodes or a suspended `TinyCUAResponseNode`.

Primary tools:

| Tool | Purpose |
|------|---------|
| `enhanced_context_retrieval` | Search scoped context and read-only exploration surfaces. |
| `digest_information` | Produce structured digested information. |

When spawned by `TinyCUAResponseNode`, the digester receives the response node's current
`session_context` via `NodeInput(messages=[...])`. It should not duplicate those input
messages in its own reusable context; it stores and propagates only new digest output.

## Related

- [`../loops/node.md`](../loops/node.md)
- [`../loops/node_queue.md`](../loops/node_queue.md)
- [`../models/digested_information.md`](../models/digested_information.md)
