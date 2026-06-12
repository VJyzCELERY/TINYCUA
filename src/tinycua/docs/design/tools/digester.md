# Information Digestion Tools

> **Status:** Target architecture

`TinyCUAInformationDigesterNode` uses information-digestion tools to gather and summarize
context for downstream nodes (`WorkerNode` or `ResponseNode`).

`InformationDigesterNode` is mandatory before `WorkerNode` (spawned by `QueryAnalyst`)
and optional before `ResponseNode` (spawned when context is insufficient).
`TaskExecutor` should use `enhanced_context_retrieval` directly instead of spawning
`InformationDigesterNode`.

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

When spawned by `QueryAnalyst` (before `WorkerNode`) or `ResponseNode`, the digester
receives a copied, selected subset of the parent's current `session_context` via
`NodeInput(messages=[...])`, plus an optional digest request payload. It should not
duplicate those input messages in its own reusable context; it stores and propagates
only new digest output.

The digester always creates a **fresh node session** — it does not inherit or reuse the
suspended parent/root session. It avoids eager loading of parent/root context and accesses
it lazily through `enhanced_context_retrieval` when needed.

The digester uses the selected-output propagation profile targeting its suspended parent.
The digest lands in the parent node's `session_context` before the parent resumes.
`chat_history` remains available for audit, but is not passed wholesale to the digester
unless explicitly selected by the parent node.

## Related

- [`../loops/node.md`](../loops/node.md)
- [`../loops/node_queue.md`](../loops/node_queue.md)
- [`../models/digested_information.md`](../models/digested_information.md)
