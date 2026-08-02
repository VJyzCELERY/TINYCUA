# Information Digestion Tools

> **Status:** Target architecture

`TinyCUAInformationDigesterNode` uses information-digestion tools to gather and summarize
context for downstream nodes (`WorkerNode` or `ResponseNode`).

`InformationDigesterNode` is spawned by `QueryAnalyst` before routing to `WorkerNode`,
or by `ResponseNode` via `suspend_current_and_prepend` when context is insufficient
for final synthesis. `TaskExecutor` should use `enhanced_context_retrieval` directly
instead of spawning `InformationDigesterNode`.

Primary tools:

| Tool | Purpose |
|------|---------|
| `enhanced_context_retrieval` | Search scoped context and read-only exploration surfaces. |
| `digest_information` | Produce structured digested information. |

`digest_information` accepts a required `context_summary` plus optional arrays for
`key_points`, `advisory_instructions`, `constraints`, and `known_gaps`. It validates
those fields and returns them with `success=true`. The runtime preserves and attaches
the original user query separately. `context_summary` is broad orientation; `key_points`
are non-binding anchors; `constraints` contain only explicit or verified requirements;
and `known_gaps` identify assumptions downstream must verify.

The tool is InformationDigester's required commit. File, session, and external
exploration remain optional and model-directed; no specific source or tool order is
required. Exploration results are returned to the model before it commits the digest.

### Enhanced Context Retrieval Cache Behavior

`enhanced_context_retrieval` lazily creates a scoped session-context cache file and runs
a limited ReAct-style search over that cache using grep/search and paginated read tools:

- Receives the current session or selected session_context.
- Lazily creates a scoped context cache file when called.
- The cache contains only selected context for that session/tool call.
- Retrieval runs as a ReAct-style search over the cache.
- Search/read tools are limited to grep/search within the cache and paginated cache reads. All search and read operations are limited to the cache.
- `InformationDigesterNode` may call the tool, but the tool owns cache creation.

When spawned by `QueryAnalyst` or `ResponseNode`,
the digester receives a copied, selected subset of the parent's current `session_context`
via `NodeInput(messages=[...])`, plus an optional digest request payload. It should not
duplicate those input messages in its own reusable context; it stores and propagates
only new digest output.

The digester always creates a **fresh node session** — it does not inherit or reuse the
suspended parent/root session identity. It inherits stable run snapshots and shared
runtime state, avoids eager loading of parent/root context, and accesses that context
lazily through `enhanced_context_retrieval` when needed.

The digester uses the selected-output propagation profile targeting its suspended parent.
The digest lands in the parent node's `session_context` before the parent resumes.
`chat_history` remains available for audit, but is not passed wholesale to the digester
unless explicitly selected by the parent node.

## Related

- [`../loops/node.md`](../loops/node.md)
- [`../loops/node_queue.md`](../loops/node_queue.md)
- [`../models/digested_information.md`](../models/digested_information.md)
