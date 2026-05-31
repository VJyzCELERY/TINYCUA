# InformationDigester Tools

> **File:** `docs/design/tools/digester.md`
> **Package:** `tinycua.tools.digester`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Overview

Two tools power the InformationDigester: `enhanced_context_retrieval` (dynamic cache
search via internal agent) and `digest_information` (structured output formatter).
Both follow the SDK `@tool` decorator pattern — type annotations + docstrings
auto-generate JSON Schema via `Tool.from_callable()`.

| Tool | Purpose | Required? |
|------|---------|-----------|
| `enhanced_context_retrieval` | Search the cached full context via internal agent | No (but informative) |
| `digest_information` | Produce structured `DigestedInformation` output | **Yes** — at least 1 call |

---

## `enhanced_context_retrieval`

### Role

Spawns an **internal agent** with a `read_context_cache` tool wired to a `.md` cache
file. The internal agent explores the cache dynamically — grep for keywords, paginate
with offset/limit — never loading the entire file at once. Returns the agent's final
response as the search result.

### Factory

```python
from tinycua_sdk.agent import Agent
from tinycua_sdk.agent.loop import BaseLoop
from tinycua_sdk.tools.decorators import Tool, tool


def create_enhanced_context_retrieval(
    cache_path: str,
    model: LanguageModel,
) -> Tool:
    """Create the enhanced context retrieval tool.

    Returns a Tool that spawns an internal Agent with a read_context_cache
    tool for dynamic file exploration (grep + offset/limit pagination).
    The internal agent:
    - Uses the same LanguageModel as InformationDigester
    - Uses the SDK's default BaseLoop (no custom loop)
    - Returns its final response as the search result
    """

    # Helper tool — wired exclusively to the cache file via closure.
    # Works like a file explorer: grep for keywords, paginate results.
    @tool
    async def read_context_cache(
        grep: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> str:
        """Search the context cache file dynamically.

        Use grep to find lines containing a keyword (case-insensitive).
        Use offset and limit to paginate through results.
        Never loads the entire file at once — explore iteratively.

        Args:
            grep: If provided, return only lines matching this pattern.
            offset: Start reading from this line number (0-indexed).
            limit: Read at most this many lines.
        """
        with open(cache_path, "r") as f:
            lines = f.readlines()

        if grep is not None:
            pattern = grep.lower()
            matching = [
                f"L{i}: {line.rstrip()}"
                for i, line in enumerate(lines)
                if pattern in line.lower()
            ]
            start = offset or 0
            end = (start + (limit or 200)) if limit is not None else None
            if end is not None:
                result = matching[start:end]
            else:
                result = matching[start:]
            if not result:
                return f"No lines matching '{grep}' found."
            shown_end = end or len(matching)
            return (
                f"Found {len(matching)} lines matching '{grep}'. "
                f"Showing lines {start}-{min(shown_end, len(matching))}:\n"
                + "\n".join(result)
            )
        else:
            start = offset or 0
            end = (start + limit) if limit is not None else len(lines)
            end = min(end, len(lines))
            result = lines[start:end]
            if not result:
                return f"No lines at offset {start}."
            return (
                f"File lines {start}-{end-1} of {len(lines)}:\n"
                + "".join(
                    f"L{i}: {line}"
                    for i, line in enumerate(result, start=start)
                )
            )

    # Main tool exposed to InformationDigester
    @tool
    async def enhanced_context_retrieval(search_query: str) -> str:
        """Search the full session context cache for relevant information.

        Spawns an internal agent with read_context_cache to dynamically
        explore the cached context file. The internal agent searches with
        grep-like patterns and paginates with offset/limit — it never loads
        the entire file at once.

        Args:
            search_query: What to search for in the context cache.
              Be specific — use keywords the internal agent can grep for.
        """
        agent = Agent(
            name="context-searcher",
            instructions=(
                "You are a context searcher. Use the read_context_cache tool to "
                "explore the full session context file. Search for information "
                "relevant to the given query. "
                "IMPORTANT: Do NOT try to read the whole file at once. Use grep "
                "to find keywords, then use offset/limit to paginate through "
                "matching sections. Return only the found information — no "
                "commentary."
            ),
            llm_model=model,
            tools=[read_context_cache],
            loop=BaseLoop(),  # default SDK loop
        )
        result_parts: list[str] = []
        async for event in agent.run(query=search_query, stream=True):
            if event["type"] == "response.output_text.delta":
                result_parts.append(event["delta"])
        return "".join(result_parts)

    return enhanced_context_retrieval  # already a Tool via @tool decorator
```

### Design Notes

- `read_context_cache` is a `@tool`-decorated helper captured via closure — only
  accessible to the internal agent
- `enhanced_context_retrieval` is also `@tool`-decorated — returned as a `Tool` to
  the calling orchestrator
- Follows the SDK factory pattern (same shape as `create_skills_list_tool`)
- Internal agent uses `BaseLoop` (SDK default) — no custom loop complexity
- Same `LanguageModel` as InformationDigester (configurable in future)
- `@tool` decorator auto-generates JSON Schema from type annotations + docstring

### Internal Agent Protocol

```
enhanced_context_retrieval(search_query: str)
  │
  └── Internal Agent ("context-searcher")
        │
        ├── Uses: read_context_cache(grep=..., offset=..., limit=...)
        │     - grep "keyword" → finds matching lines
        │     - offset=0, limit=20 → paginates results
        │     - Never loads full file — explores dynamically
        │
        └── Returns: final text response (found information)
```

---

## `digest_information`

### Role

The **primary output mechanism** for InformationDigester. Instead of parsing the
agent's final text response, the orchestrator extracts `DigestedInformation` from
this tool's call result. The agent MUST call this at least once before stopping.

### Definition

```python
from tinycua_sdk.tools.decorators import tool
from tinycua.state.digested_information import DigestedInformation


# Unique identifier prefix — distinguishes from other tool call results
DIGEST_OUTPUT_PREFIX = "DIGEST_INFO::"

@tool
async def digest_information(
    context_summary: str,
    key_points: list[str],
    advisory_instructions: str | None = None,
    constraints: list[str] | None = None,
    known_gaps: list[str] | None = None,
) -> str:
    """Format findings into structured DigestedInformation output.

    You MUST call this tool at least once before stopping. Subsequent
    calls replace your previous output (last call wins).

    Args:
        context_summary: Compressed relevant context in markdown.
        key_points: Key takeaway points for downstream agents.
        advisory_instructions: Action-oriented guidance.
        constraints: Guardrails and constraints for downstream agents.
        known_gaps: Information gaps that could not be filled.
    """
    result = DigestedInformation(
        context_summary=context_summary,
        key_points=key_points,
        advisory_instructions=advisory_instructions,
        constraints=constraints,
        known_gaps=known_gaps,
    )
    return f"{DIGEST_OUTPUT_PREFIX}{result.to_json()}"
```

### Design Notes

- `@tool` decorator generates JSON Schema from type annotations + docstring
- `DIGEST_OUTPUT_PREFIX` allows the orchestrator to distinguish this tool's result
  from `enhanced_context_retrieval` results in the event stream
- The agent MUST call this at least once — enforced by `InformationDigestionLoop`
- Subsequent calls replace the previous output (last call wins in `_parse_digested_output`)
- Mirrors `DigestedInformation` fields exactly — no mapping or transformation needed

### Output Parsing (orchestrator-side)

The orchestrator scans tool call events for `digest_information`, extracts the
prefixed result, and deserializes it:

```python
def _parse_digested_output(self, events: list[dict]) -> DigestedInformation | None:
    """Extract DigestedInformation from the LAST digest_information tool call."""
    for event in reversed(events):
        if event.get("type") != "response.tool_call":
            continue
        if event.get("tool_name") != "digest_information":
            continue
        result_str = event.get("output", "")
        if result_str.startswith(DIGEST_OUTPUT_PREFIX):
            json_str = result_str[len(DIGEST_OUTPUT_PREFIX):]
            return DigestedInformation.from_json(json_str)
    return None
```

---

## Integration

```python
# In InformationDigester.run():
cache_path = self._write_context_cache()

retrieval_tool = create_enhanced_context_retrieval(
    cache_path=cache_path,
    model=self.config.model,
)
tools = [
    retrieval_tool,
    digest_information,
    *self.config.extra_tools,
]
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Internal agent for retrieval | `Agent` with `BaseLoop` + `read_context_cache` closure | Dynamic exploration (grep + pagination); never loads full file |
| SDK factory pattern | `@tool` on closure functions, return Tool | Same as `create_skills_list_tool`; auto-generated JSON Schema |
| Output from tool call | `digest_information` tool, NOT agent final text | Structured output guaranteed; no JSON parsing fragility |
| Output identifier | `DIGEST_OUTPUT_PREFIX` prefix on return string | Distinguishes from other tool results in event stream |
| Last call wins | Subsequent `digest_information` calls replace previous | Agent can refine output across iterations |
| Same model | Internal agent inherits InformationDigester's model | Simpler; configurable in future |


---


---


---

## See also

Prev : [Orchestrator-Call Tools](agent_calls.md) | Next : [Task Tools](task.md)


## Related

- [InformationDigester orchestrator](../agents/information_digester.md)
- [DigestedInformation output](../state/digested_information.md)
- [@tool decorator (SDK)](../config/../../../../tinycua-sdk/tinycua_sdk/tools/decorators.py)
- [InformationDigestionLoop + mandatory digest enforcement](../loops/information_digestion_loop.md)
