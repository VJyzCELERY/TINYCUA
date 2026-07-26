# TinyCUAInformationDigesterNode

> **Package:** `tinycua.loops.information_digester`
> **Status:** Target architecture

## Role

`TinyCUAInformationDigesterNode` is a concrete `ProcessNode` that gathers and digests
context for downstream nodes. It is spawned by `QueryAnalyst` before routing to
`WorkerNode`, or by `ResponseNode` via `suspend_current_and_prepend` when context
is insufficient for final synthesis.

## Non-Responsibilities

- Does not execute tasks.
- Does not create or mutate tasks.
- Does not synthesize final user responses (it provides digested context for
  WorkerNode and ResponseNode).

## Inputs

- `NodeInput` with copied, selected subset of QueryAnalyst's `session_context` messages.
- Optional digest request payload.
- When spawned by ResponseNode (via `suspend_current_and_prepend`): copied session_context
  from the suspended response node's session.

## Session Scope

InformationDigester always creates a **fresh node session**. It does not inherit
or reuse the suspended parent/root session. Specific rules:

- **Fresh session**: Digester creates a new session with its own `session_id`. It
  does not copy or inherit the parent `session_id` or root session.
- **Stable run context**: The child session inherits the root date, environment,
  project-instruction snapshots, and shared runtime state so every node in one run
  uses the same authoritative context.
- **Selected input only**: Digester receives only the selected `NodeInput` messages
  from the parent. It does not receive the full parent `session_context`.
- **Lazy context access**: Digester accesses root/parent context lazily through
  `enhanced_context_retrieval` when needed, rather than eagerly loading broad
  context into its session.
- **Own output only**: Digester stores only its own new local output (the digest)
  in its session. It does not re-store copied input messages in its reusable context.
- **Forward to parent**: On termination, Digester forwards its output to the
  suspended parent node rather than committing it directly upward to root/parent.
  The digest becomes part of the parent's input via selected-output propagation.

## Outputs / State Produced

- Structured `DigestedInformation` for downstream consumption (WorkerNode or
  ResponseNode), built from the successful `digest_information` tool result.
- The original user query is attached by the runtime rather than repeated by the model.

## Tools

| Tool Scope | Description |
|------------|-------------|
| Read-only file tools | Inspect explicitly referenced workspace files. |
| `enhanced_context_retrieval` | Search scoped session context. |
| `web_search` / `fetch_url` | Resolve remaining material external uncertainty. |
| `digest_information` | Produce structured digested information. |

`digest_information` is the Digester's required commit. Exploration tools remain
optional, but an exploratory tool result cannot complete the node by itself. The
runtime returns that result to the model for another turn. A successful structured
digest commit completes the node directly.

### Information Priority

The prompt advises the digester to inspect explicitly referenced workspace files first,
then search session context, then use external research only if material uncertainty
remains. It honors the requested timeframe, prefers authoritative sources, and stops once
planning has reliable context. This is guidance, not a deterministic tool-order gate;
task execution remains downstream.

### Enhanced Context Retrieval Cache Behavior

`enhanced_context_retrieval` lazily creates a scoped session-context cache file and runs
a limited ReAct-style search over that cache:

- Receives the current session or selected session_context.
- Lazily creates a scoped context cache file when called.
- The cache contains only selected context for that session/tool call.
- Search/read tools are limited to grep/search within the cache and paginated cache reads.

## Queue Behavior / `on_complete()`

```text
InformationDigester completes:
  → Require a successful digest_information commit.
  → Propagate digested output to parent node's session via selected-output
    propagation rule.
  → Advance queue; parent node resumes.
```

## Propagation

- Uses selected-output propagation profile targeting its suspended parent.
- The digest lands in the parent node's `session_context`.
- `chat_history` remains available for audit but is not passed wholesale to the
  digester unless explicitly selected.
- Does not re-store copied input messages in its own reusable context; stores and
  propagates only new digest output.
- Parent nodes (WorkerNode, ResponseNode) can detect whether digestion has already
  occurred by checking `session_context` for existing digest output.

## Failure / Retry Behavior

Retry according to `NodeRetryPolicy`. Missing or failed digest commits do not advance
the queue. Digest failure may prevent WorkerNode from having sufficient context for
routing decisions, or ResponseNode from having sufficient context for final synthesis.

## Related Config

- `NodeToolPolicy` — `enhanced_context_retrieval` and `digest_information` scope.
- `NodeRetryPolicy` — retry behavior.

## Related

- [`node.md`](node.md)
- [`node_queue.md`](node_queue.md)
- [`../tools/digester.md`](../tools/digester.md)
- [`../models/digested_information.md`](../models/digested_information.md)
