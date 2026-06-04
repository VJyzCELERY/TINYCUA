# Information Digestion Tools

> **Status:** Target architecture

`TinyCUAInformationDigesterNode` uses information-digestion tools to gather and summarize
context for downstream nodes or a suspended `TinyCUAResponseNode`.

`InformationDigesterNode` is optional and invoked only when direct accumulated context/tool access is insufficient. InformationDigesterNode is optional and invoked only when direct context/tool access is insufficient. `ResponseNode` should first evaluate whether accumulated context is enough. `TaskExecutor` should use `enhanced_context_retrieval` directly instead of spawning `InformationDigesterNode`.

Primary tools:

| Tool | Purpose |
|------|---------|
| `enhanced_context_retrieval` | Search scoped context and read-only exploration surfaces. |
| `digest_information` | Produce structured digested information. |

### Enhanced Context Retrieval Cache Behavior

`enhanced_context_retrieval` lazily creates a scoped session-context cache file and runs
a limited ReAct-style search over that cache using grep/search and paginated read tools:

- Receives the current session or selected session_context.
- Lazily creates a scoped context cache file when called.
- The cache contains only selected context for that session/tool call.
- Retrieval runs as a ReAct-style search over the cache.
- Search/read tools are limited to grep/search within the cache and paginated cache reads. All search and read operations are limited to the cache.
- `InformationDigesterNode` may call the tool, but the tool owns cache creation.

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
