# Tool Constants and Node Tool Scope

> **Status:** Target architecture

TinyCUA nodes expose tools through the tool policy defined in
[`../config/node_config.md`](../config/node_config.md).

The outer SDK `Agent(tools=[...])` remains the caller-provided tool pool. TinyCUA chooses
which nodes can see those tools.

| Node | Tool Scope |
|------|------------|
| TinyCUAQueryAnalystNode | classification + read-only task/context tools |
| TinyCUAInformationDigesterNode | read-only file/web exploration + enhanced retrieval + digest tools |
| TinyCUAWorkerNode | worker decision tools only |
| TinyCUATaskCreateNode | deterministic root task creation tools (TaskInit/TaskCreate) |
| TinyCUATaskAnalyzerNode | task structure tools; TaskInit/TaskCreate only when recreation is requested |
| TinyCUATaskAssessorNode | task assessment/read/update tools as needed |
| TinyCUATaskExecutorNode | task execution tools + selected outer Agent tools + `enhanced_context_retrieval` + exploration/web/context search tools when enabled |
| TinyCUAResultReviewerNode | review/decision tools |
| TinyCUAResponseNode | same base toolset as TinyCUATaskExecutorNode + final response/synthesis behavior + optional information-digestion request capability only when enabled |

## TaskExecutor Direct Context Retrieval

`TaskExecutor` does not spawn `InformationDigesterNode`. If `TaskExecutor` needs more
context, it calls `enhanced_context_retrieval` directly.

## WorkerNode Information Digestion

`QueryAnalyst` spawns `InformationDigesterNode` before routing to `WorkerNode`.
The digester gathers and digests context, then propagates the output to the Worker's
session. Worker receives DigestedInformation as input and uses it for routing decisions.

## ResponseNode Same Base Toolset

`ResponseNode` has the same base toolset as `TaskExecutor`, plus final response/synthesis
behavior and optional information-digestion request capability only when enabled.

## Enhanced Context Retrieval

`enhanced_context_retrieval` is a tool available to `InformationDigesterNode`,
`TaskExecutor`, and `ResponseNode`:

- Receives the current session or selected session_context.
- Lazily creates a scoped context cache file when called.
- The cache contains only selected context for that session/tool call.
- Retrieval runs as a ReAct-style search over the cache.
- Search/read tools are limited to grep/search within the cache and paginated cache reads.
- `InformationDigesterNode` may call the tool, but the tool owns cache creation.

## `fetch_url` Pagination Contract

`fetch_url` converts HTML to Markdown before slicing model-visible content by character.
`offset` is a non-negative character offset; `limit` is 1 through 50,000 and defaults to
50,000. The independent `max_size` bound limits source bytes used for conversion and
defaults to 102,400.

Results include `returned_chars`, `total_chars`, `truncated`, `source_truncated`,
`next_offset`, and `final_url`. `truncated` means another converted-character page exists;
`source_truncated` means the source-byte bound was hit. `next_offset` appears only when
another character page exists. Out-of-range offsets return a successful empty final page,
and errors retain the pagination metadata. Each page refetches the URL, so pagination
cannot recover source bytes excluded by `max_size`.

`fetch_url` and `web_search` accept `load_cache=false` by default. Successful
session-local observations receive an opaque `cache_id`. With `load_cache=true`,
the tool returns only an exact cached request without contacting the network.
Default calls contact the network first and, on failure, return clearly labeled
cached fallback evidence when available. Search exact loads require the same
normalized query and `max_results`; automatic fallback may use a compatible
same-query cached result and reports its cached result count and timestamp.
`fetch_url` rejects Cloudflare responses with `cf-mitigated: challenge` and
the paired `Quick verification` / `Confirm you're human` interstitial text as
failed observations, so they are never cached as page evidence.

## Related

- [`../config/node_config.md`](../config/node_config.md)
- [`../tools/digester.md`](../tools/digester.md)
- [`../tools/task.md`](../tools/task.md)
