# Information Digestion Tools

> **Status:** Target architecture

`TinyCUAInformationDigesterNode` uses information-digestion tools to gather and summarize
context for downstream nodes or a suspended `TinyCUAResponseNode`.

Primary tools:

| Tool | Purpose |
|------|---------|
| `enhanced_context_retrieval` | Search scoped context and read-only exploration surfaces. |
| `digest_information` | Produce structured digested information. |

When spawned by `TinyCUAResponseNode`, the digester receives a copied, selected subset of
the response node's current `session_context` via `NodeInput(messages=[...])`, plus an
optional digest request payload. It should not duplicate those input messages in its own
reusable context; it stores and propagates only new digest output.

The digester uses the selected-output propagation profile targeting its suspended parent.
The digest lands in the parent response node's `session_context` before the response node
resumes final synthesis. `chat_history` remains available for audit, but is not passed
wholesale to the digester unless explicitly selected by the response node.

## Related

- [`../loops/node.md`](../loops/node.md)
- [`../loops/node_queue.md`](../loops/node_queue.md)
- [`../models/digested_information.md`](../models/digested_information.md)
