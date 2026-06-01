# InformationDigester Tools

> **File:** `docs/design/tools/digester.md`
> **Package:** `tinycua.tools.digester`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Overview

Two tools power the InformationDigester:

| Tool | Purpose | Required? |
|------|---------|-----------|
| `enhanced_context_retrieval` | Spawn inner transient retrieval agents over context cache + read-only exploration tools | No |
| `digest_information` | Produce structured digest output | **Yes** — at least one call |

---

## `enhanced_context_retrieval`

### Role

Spawns an internal transient retrieval agent. That inner agent receives **two separate
toolsets**:

```text
CONTEXT_CACHE_TOOLS = [grep_context, read_context]
EXPLORATION_TOOL = [FileReadTool, FileListTool, WebSearchTool]
```

Cache tools (`grep_context`, `read_context`) are scoped strictly to the
InformationDigester context cache. Exploration tools (`FileReadTool`, `FileListTool`,
`WebSearchTool`) are used when the context cache is insufficient.

### Factory

```text
create_enhanced_context_retrieval(
    cache_path: str,
    model: LanguageModel,
    exploration_tools: list[Tool] = EXPLORATION_TOOL,
) → tinycua_sdk.Tool

  · grep_context(pattern: str, offset: int? = None, limit: int? = None) → str
      - searches only cache_path

  · read_context(offset: int = 0, limit: int = 200) → str
      - reads only cache_path

  · enhanced_context_retrieval(search_query: str) → str
      - inner_agent = Agent(
          name="context-searcher",
          instructions=CONTEXT_SEARCHER_INSTRUCTION,
          llm_model=model,
          tools=[grep_context, read_context, *exploration_tools],
          loop=BaseLoop(),
        )
      - run inner_agent on search_query
      - return final text findings
```

### Inner Agent Protocol

```text
enhanced_context_retrieval(search_query)
  → internal transient Agent("context-searcher")
      1. First understand cached session context using grep_context/read_context.
      2. If cache is insufficient, use EXPLORATION_TOOL for read-only exploration.
      3. Return concise evidence-focused findings.
```

The retrieval tool can be called multiple times in parallel by InformationDigester for
different search queries.

---

## `digest_information`

### Role

The primary output mechanism for InformationDigester. The loop extracts structured
digest data from this tool's call result and writes `InformationDigesterState`.

```text
DIGEST_OUTPUT_PREFIX = "DIGEST_INFO::"

digest_information(
    context_summary: str,
    key_points: list[str],
    advisory_instructions: str | None = None,
    constraints: list[str] | None = None,
    known_gaps: list[str] | None = None,
) → str
    · result = DigestedInformation(...)
    · return f"{DIGEST_OUTPUT_PREFIX}{result.to_json()}"
```

`InformationDigestionLoop` enforces that this tool is called at least once. Last call
wins if the agent refines its digest.

---

## Integration

```text
cache_path = self._write_context_cache()
retrieval_tool = create_enhanced_context_retrieval(
    cache_path=cache_path,
    model=self.session.agent_state.agent_config.model,
    exploration_tools=EXPLORATION_TOOL,
)
tools = [retrieval_tool, digest_information, *self.session.agent_state.agent_config.extra_tools]
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Split cache/exploration tools | `CONTEXT_CACHE_TOOLS` + `EXPLORATION_TOOL` | Cache access remains scoped; exploration remains read-only |
| Inner transient agent | `Agent` with BaseLoop | Focused retrieval tasks without polluting parent session_context |
| Parallel retrieval allowed | Multiple retrieval calls | Digester can fan out multiple queries |
| Digest via tool | `digest_information`, not final text parsing | Structured output guaranteed |
| Last digest wins | Later digest call replaces earlier | Allows refinement |
| Config from session | `session.agent_state.agent_config` | Session is source of truth |

---

## See also

Prev : [AgentNode-Call Tools](agent_calls.md) | Next : [Task Tools](task.md)

## Related

- [InformationDigester AgentNode](../agent_node/information_digester.md)
- [InformationDigesterState](../state/information.md#informationdigesterstate)
- [EXPLORATION_TOOL](../constants/tools.md)
- [InformationDigestionLoop](../loops/information_digestion_loop.md)
