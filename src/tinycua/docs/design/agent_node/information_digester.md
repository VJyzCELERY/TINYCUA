# Information Digester

> **File:** `docs/design/agent_node/information_digester.md`
> **Package:** `tinycua.agent_nodes.information_digester`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`InformationDigester` retrieves and digests information from a QueryAnalyst-produced
state or plain query. It is transient (`is_transient=True`) and its output is consumed
inline by TinyCUAWorker or downstream TaskAnalyzer.

Unlike QueryAnalyst, it does not frontload full context into `session_context`.
Instead, it creates a context cache and exposes scoped retrieval tools to inner
transient exploration agents.

---

## Session

```text
__init__(config: InformationDigesterConfig | None) -> None
  → super().__init__(config=config, session=None)
  → mark session.is_transient = True
```

On termination, chat_history/token/failure propagate, but session_context does not.

---

## `run()` Method

```text
run(query: str) -> AsyncIterator[dict]
```

`query` may be plain text or include AgentState YAML front-matter. The receiver owns
parsing:

```text
parsed = AgentState.from_string(query)
if isinstance(parsed, QueryAnalystState):
    context_hint = parsed.context
    user_query = parsed.query
else:
    context_hint = None
    user_query = query
```

---

## Context Cache

InformationDigester pulls context from the parent and active session, writes it to a
markdown cache, and lets tools search that cache dynamically.

```text
_write_context_cache()
  parent = self.session.parent
  collect parent.get_messages()
  collect active descendant messages if different
  format as markdown
  write cache file
  return cache_path
```

The cache is cleaned in `finally` after `run()` finishes.

---

## Enhanced Context Retrieval Tool

`enhanced_context_retrieval(query: str)` spawns one or more small transient inner
agents. These agents are exploratory workers that search for relevant context and
return concise findings to InformationDigester.

### Inner agent tools

Inner retrieval agents receive two tool groups:

```text
CONTEXT_CACHE_TOOLS = [grep_context, read_context]
EXPLORATION_TOOL = [FileReadTool, FileListTool, WebSearchTool]
```

| Tool Group | Scope | Purpose |
|------------|-------|---------|
| `grep_context` / `read_context` | Strictly limited to the context cache | Search/read cached session context |
| `EXPLORATION_TOOL` | Read-only project/web exploration | Gather external or project context as needed |

The context-cache tools cannot operate outside the cache. `EXPLORATION_TOOL` is read-only.

### Parallel retrieval

The enhanced retrieval tool should support parallel use: InformationDigester can call
it multiple times with different search queries, and each call may spawn a separate
transient retrieval agent.

### Inner agent instruction

Inner retrieval agents must be instructed to:

1. Understand the cached context first using `grep_context` / `read_context`.
2. Use `EXPLORATION_TOOL` only when cache context is insufficient.
3. Return concise evidence-focused findings.

---

## Digest Output

InformationDigester must call `digest_information` at least once. The loop enforces
this and writes `InformationDigesterState` to `session.agent_state`.

```text
InformationDigesterState(
  type="information_digester",
  status="terminated",
  failure=0,
  context_summary="...",
  key_points=[...],
  advisory_instructions="...",
  constraints=[...],
  known_gaps=[...],
  retrieval_iterations=N,
)
```

The state is serializable via `to_yaml()` and reconstructable with
`AgentState.from_string(...)`.

---

## Complete AgentNode

```text
InformationDigester(BaseAgentNode)  ← transient

run(query: str) -> AsyncIterator[dict]
  · parsed_state = AgentState.from_string(query)
  · try:
      → cache_path = _write_context_cache()
      → build instruction: base + parsed QueryAnalystState summary if present
      → create enhanced_context_retrieval(cache_path, model,
          tools=[grep_context, read_context, *EXPLORATION_TOOL])
      → create SDK Agent(tools=[enhanced_context_retrieval, digest_information, *extra_tools],
          loop=InformationDigestionLoop(session=self.session))
      → agent.run(query=query, messages=self.session.session_context, stream=True)
      → yield events
    finally:
      → _cleanup_cache()
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Transient session | `is_transient=True` | Output consumed inline |
| Cache not frontload | Full context in markdown cache | Avoids compaction and lets retrieval be dynamic |
| Inner retrieval agents | Spawned by enhanced retrieval tool | Enables multiple focused searches |
| Split tool groups | Cache tools + `EXPLORATION_TOOL` | Cache-scoped search remains safe; exploration remains read-only |
| Parallel retrieval | Multiple retrieval calls allowed | Digester can fan out different queries |
| Mandatory digest | `digest_information` enforced by loop | Structured output guaranteed |
| AgentState output | `InformationDigesterState` | Self-serializing cross-node state |

---

## See also

Prev : [`QueryAnalyst`](query_analyst.md) | Next : [`TaskAnalyzer`](task_analyzer.md)

## Related

- [InformationDigesterState](../state/information.md#informationdigesterstate)
- [DigestedInformation fields](../state/digested_information.md)
- [EXPLORATION_TOOL](../constants/tools.md)
- [Enhanced context tools](../tools/digester.md)
