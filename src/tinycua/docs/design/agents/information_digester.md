# Information Digester

> **File:** `docs/design/agents/information_digester.md`
> **Package:** `tinycua.agents.information_digester`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`InformationDigester` retrieves and digests information from the context-enhanced
query produced by QueryAnalyst. It is **transient** (`is_transient = True`) — never
registered in parent's `child_sessions`. Chat history propagates on termination,
session_context does not.

Its output (`DigestedInformation`) is consumed inline by the Worker — no persistence
in the session tree.

---

## Key Design Difference from QueryAnalyst

| Aspect | QueryAnalyst | InformationDigester |
|--------|-------------|-------------------|
| Context loading | Front-loaded into `session_context` with cascading compaction | Cached as `.md` file; searched dynamically via tool |
| Compaction | Compacts combined parent + active context | Does NOT compact — full context written to cache |
| Retrieval | None — reads from own `session_context` | `enhanced_context_retrieval` tool searches cache via internal agent |
| Output parsing | Agent final text response → JSON parse | `digest_information` tool call → structured `DigestedInformation` |
| Enforcement | No mandatory tool calls | At least 1 `digest_information` call required |

---

## Session

`InformationDigester` creates its own transient session.

```python
def __init__(self, config: InformationDigesterConfig | None = None):
    if config is None:
        config = InformationDigesterConfig()
    super().__init__(config=config, session=None)
    self.session.is_transient = True
```

## Context Assembly + Cache

Like QueryAnalyst, InformationDigester pulls context from the parent session.
Unlike QueryAnalyst, it does **not** frontload this into `session_context`.
Instead it writes the full context to a cache file and lets the `enhanced_context_retrieval`
tool search it dynamically.

```python
import os
import tempfile
from uuid import uuid4


class InformationDigester(BaseAgentOrchestrator[InformationDigesterState]):

    _cache_path: str | None = None  # path to the .md cache file

    def _write_context_cache(self) -> str:
        """Pull parent + active-agent context, write to a .md cache file.

        Returns the path to the cache file. The file is removed when
        InformationDigester finishes (see _cleanup_cache).
        """
        parent = self.session.parent
        if parent is None:
            return ""

        # Gather full context (same pattern as QueryAnalyst)
        parent_context = parent.get_messages()
        active_session = parent.get_active_session()
        active_context = (
            active_session.get_messages()
            if active_session is not parent
            else []
        )

        # Build markdown cache
        md_lines = [
            "# Full Session Context",
            "",
            "## Parent Session Context",
            *self._format_context(parent_context),
            "",
        ]
        if active_context:
            md_lines.extend([
                "## Active Agent Session Context",
                *self._format_context(active_context),
                "",
            ])

        # Write to temp file (absolute path)
        cache_path = os.path.abspath(os.path.join(
            tempfile.gettempdir(),
            f"tinycua_digester_{uuid4().hex}.md",
        ))
        with open(cache_path, "w") as f:
            f.write("\n".join(md_lines))

        self._cache_path = cache_path
        return cache_path

    def _format_context(self, messages: list[dict]) -> list[str]:
        """Format role/content messages as markdown."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"**{role}**: {content}")
            lines.append("")
        return lines

    def _cleanup_cache(self) -> None:
        """Remove the cache file if it exists."""
        if self._cache_path and os.path.exists(self._cache_path):
            os.remove(self._cache_path)
            self._cache_path = None
```

---

## Tools

InformationDigester uses exactly two tools:

| Tool | Purpose | Required? |
|------|---------|-----------|
| `enhanced_context_retrieval` | Search the cached full context via internal agent | No (but informative) |
| `digest_information` | Produce structured `DigestedInformation` output | **Yes** — at least 1 call |

### `enhanced_context_retrieval`

A tool that runs an **internal agent** with a `read_context_cache` tool wired to the
cache file. The internal agent searches the cached context based on a search query
and returns relevant findings.

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

**Design notes:**
- Both `read_context_cache` and `enhanced_context_retrieval` are `@tool`-decorated —
  follows the SDK factory pattern (same as `create_skills_list_tool`)
- `read_context_cache` is captured via closure, used only by the internal agent
- The internal agent uses `BaseLoop` (SDK default) — no custom iteration logic
- The same `LanguageModel` as InformationDigester is used (configurable in future)
- The `@tool` decorator auto-generates JSON Schema from type annotations + docstring

### `digest_information`

A tool that formats findings into `DigestedInformation`. This is the **primary output
mechanism** — the orchestrator reads the result from this tool call, not from the
agent's final text response.

```python
from tinycua_sdk.tools.decorators import tool
from tinycua.state.digested_information import DigestedInformation


# Unique identifier prefix for digest_information outputs
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

**Design notes:**
- `@tool` decorator generates JSON Schema from type annotations + docstring
- The `DIGEST_OUTPUT_PREFIX` allows the orchestrator to distinguish this tool's result
  from `enhanced_context_retrieval` results
- The agent MUST call this at least once — enforced by `InformationDigestionLoop`
- Subsequent calls replace the previous output (last call wins in `_parse_digested_output`)
- The tool mirrors `DigestedInformation` fields exactly — no mapping needed

---

## Output Parsing

Unlike other orchestrators that parse the agent's final text response, InformationDigester
extracts the `DigestedInformation` from the `digest_information` tool call result:

```python
def _parse_digested_output(self, events: list[dict]) -> DigestedInformation | None:
    """Extract DigestedInformation from digest_information tool call results.

    Scans all tool_call events for digest_information calls, takes the
    LAST one (subsequent calls replace previous output). Parses the
    DIGEST_OUTPUT_PREFIX result into a DigestedInformation object.
    """
    for event in reversed(events):
        if event.get("type") != "response.tool_call":
            continue
        if event.get("tool_name") != "digest_information":
            continue

        # Tool result is in the event output (accumulated after stream)
        result_str = event.get("output", "")
        if result_str.startswith(DIGEST_OUTPUT_PREFIX):
            json_str = result_str[len(DIGEST_OUTPUT_PREFIX):]
            return DigestedInformation.from_json(json_str)

    return None  # No digest_information call found (error)
```

---

## Loop

`InformationDigestionLoop` enforces the "at least 1 digest_information call" rule
alongside the existing gap-evaluation logic:

```python
class InformationDigestionLoop(BaseLoop):
    """Iterative retrieval with mandatory digest_information call.

    Extends SDK BaseLoop to:
    - Increment retrieval_iterations each cycle
    - Track whether digest_information has been called
    - Prevent stopping until at least 1 digest call has been made
    """

    def __init__(
        self,
        state: InformationDigesterState,
        max_iterations: int | None = None,
    ):
        super().__init__()
        self.state = state
        self.max_iterations = max_iterations
        self._digest_called = False

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        self.state.retrieval_iterations = 0
        self._digest_called = False

        async for event in super().run(agent, messages, tools, override_instructions, stream=True):
            # Track digest_information calls
            if event.get("type") == "response.tool_call":
                if event.get("tool_name") == "digest_information":
                    self._digest_called = True
                self.state.retrieval_iterations += 1
            yield event

    def can_stop(self, events: list[dict]) -> bool:
        """Extend stop condition: must have called digest_information."""
        if not self._digest_called:
            return False
        # Delegate to parent for sufficiency checks
        return super().can_stop(events)
```

**Stop conditions (revised):**
1. LLM-judged sufficiency AND `digest_information` has been called at least once
2. OR `max_iterations` cap reached (if set) — digester stops even without digest call

---

## Complete Orchestrator

```python
import json
import os
import tempfile
from collections.abc import AsyncIterator
from uuid import uuid4

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import InformationDigesterConfig
from tinycua.constants.tools import INFORMATION_DIGESTER_BASE_TOOLS
from tinycua.loops.information_digestion_loop import InformationDigestionLoop
from tinycua.state.information import InformationDigesterState
from tinycua.state.digested_information import DigestedInformation
from tinycua.tools.digester import (
    create_enhanced_context_retrieval,
    digest_information,
    DIGEST_OUTPUT_PREFIX,
)


class InformationDigester(BaseAgentOrchestrator[InformationDigesterState]):
    """Information digestion — transient agent with cached context search.

    Pulls full parent + active-agent context into a .md cache file.
    Uses enhanced_context_retrieval (internal agent + read_file)
    to dynamically search the cache.
    Output is extracted from digest_information tool calls, not from
    the agent's final text response.
    """

    config: InformationDigesterConfig
    _cache_path: str | None = None

    def __init__(self, config: InformationDigesterConfig | None = None):
        if config is None:
            config = InformationDigesterConfig()
        super().__init__(config=config, session=None)
        self.session.is_transient = True

    # ── Main entry point ─────────────────────────────────────────────

    async def run(
        self,
        ceq: "ContextEnhancedQuery",
    ) -> AsyncIterator[dict]:
        """Digest information from the context-enhanced query.

        Args:
            ceq: ContextEnhancedQuery from QueryAnalyst
                (context=analysis output, query=original user_query)
        """
        try:
            # 1. Write full parent context to cache file
            cache_path = self._write_context_cache()

            # 2. Build instruction: base + CEQ context + cache reference
            instructions = self.build_instruction({
                "context_enhanced_query": ceq,
            })

            # 3. Build query: the CEQ analysis + original query
            query = json.dumps({
                "analysis": ceq.context,
                "user_query": ceq.query,
            })

            # 4. Build dynamic tools (cache path captured in closure)
            retrieval_tool = create_enhanced_context_retrieval(
                cache_path=cache_path,
                model=self.config.model,
            )
            tools = [
                retrieval_tool,
                digest_information,
                *self.config.extra_tools,
            ]

            # 5. Build SDK Agent per-call
            agent = Agent(
                name=self.config.name,
                instructions=instructions,
                llm_model=self.config.model,
                tools=tools,
                loop=InformationDigestionLoop(
                    state=self.state,
                    max_iterations=self.config.max_iterations_override,
                ),
            )

            # 6. Stream — accumulate events for output parsing
            events: list[dict] = []
            async for event in agent.run(query=query, stream=True):
                events.append(event)
                yield event

            # 7. Parse output from digest_information tool call (NOT final text)
            self.state.digested_information = self._parse_digested_output(events)
            self.state.last_result = (
                self.state.digested_information.to_dict()
                if self.state.digested_information
                else None
            )

        finally:
            self._cleanup_cache()

    # ── Context cache ────────────────────────────────────────────────

    def _write_context_cache(self) -> str:
        """Pull parent + active-agent context, write to .md cache file."""
        parent = self.session.parent
        if parent is None:
            return ""

        parent_context = parent.get_messages()
        active_session = parent.get_active_session()
        active_context = (
            active_session.get_messages()
            if active_session is not parent
            else []
        )

        md_lines = [
            "# Full Session Context",
            "",
            "## Parent Session Context",
            *self._format_context(parent_context),
            "",
        ]
        if active_context:
            md_lines.extend([
                "## Active Agent Session Context",
                *self._format_context(active_context),
                "",
            ])

        cache_path = os.path.abspath(os.path.join(
            tempfile.gettempdir(),
            f"tinycua_digester_{uuid4().hex}.md",
        ))
        with open(cache_path, "w") as f:
            f.write("\n".join(md_lines))

        self._cache_path = cache_path
        return cache_path

    def _format_context(self, messages: list[dict]) -> list[str]:
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"**{role}**: {content}")
            lines.append("")
        return lines

    def _cleanup_cache(self) -> None:
        if self._cache_path and os.path.exists(self._cache_path):
            os.remove(self._cache_path)
            self._cache_path = None

    # ── Output parsing ───────────────────────────────────────────────

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

    # ── Instruction ──────────────────────────────────────────────────

    def build_instruction(self, context: dict[str, Any]) -> str:
        base = self.config.instructions  # INFORMATION_DIGESTER_INSTRUCTION
        ceq = context.get("context_enhanced_query")
        return f"{base}\n\n{self._build_dynamic_context(ceq)}"

    def _build_dynamic_context(self, ceq) -> str:
        if ceq is None:
            return ""
        return (
            f"---\n"
            f"Query Analyst Context Analysis:\n{ceq.context}\n\n"
            f"Original User Query:\n{ceq.query}\n"
        )
```

---

## Config

`InformationDigesterConfig` — `name="information-digester"`,
`instructions=INFORMATION_DIGESTER_INSTRUCTION`, `max_iterations_override: int | None`.

`max_iterations_override=None` means no iteration limit. See
[`config/agents.md`](../config/agents.md#informationdigesterconfig).

---

## State

`InformationDigesterState` — `digested_information: DigestedInformation | None`,
`retrieval_iterations: int`.

See [`state/information.md`](../state/information.md#informationdigesterstate).

---

## Loop

`InformationDigestionLoop(state=self.state, max_iterations=...)` — iterative retrieval
with mandatory `digest_information` call enforcement. Gap evaluation between SDK iterations.

See [`loops/information_digestion_loop.md`](../loops/information_digestion_loop.md).

---

## Tools

| Constant | Contents | Purpose |
|----------|----------|---------|
| `INFORMATION_DIGESTER_BASE_TOOLS` | `[]` (empty) | Both tools are built dynamically in `run()` |
| `enhanced_context_retrieval` | Created via `create_enhanced_context_retrieval(cache_path, model)` | Internal agent searching cached context |
| `digest_information` | `@tool` decorator | Formats findings into `DigestedInformation` |

See [`constants/tools.md`](../constants/tools.md) and `tinycua/tools/digester.py`.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Transient session | `is_transient = True`; chat_history propagates | Output consumed inline; audit trail preserved |
| Context cache vs frontload | Full context in `.md` cache, searched dynamically | No compaction overhead; full context available to search tool |
| Cache lifetime | Created in `run()`, cleaned up in `finally` | Guarantees cleanup even on exceptions |
| Internal search agent | `Agent` with `BaseLoop` + `read_context_cache` (grep + offset/limit) | Dynamic file exploration; never loads full file at once |
| Cache path | Absolute via `os.path.abspath` + `tempfile.gettempdir()` | Safe cleanup; no relative path ambiguity |
| SDK tool factory | `@tool` decorator on closure functions | Follows SDK pattern; auto-generates JSON Schema from type annotations + docstring |
| Output from tool call | `digest_information` tool, NOT agent final text | Structured output guaranteed; no JSON parsing fragility |
| Output identifier | `DIGEST_OUTPUT_PREFIX` prefix on tool result string | Distinguishes from other tool call results |
| Last call wins | Subsequent `digest_information` calls replace previous | Agent can refine its output across iterations |
| At least 1 digest call | Loop enforces `_digest_called` before stop | Ensures output is always produced |
| No max_iterations by default | `max_iterations_override=None` | Agent stops when sufficiency met + digest called |
| Same model for all agents | Internal agent uses InformationDigester's model | Simpler; configurable in future |
| Cache as markdown | `**role**: content` format | Readable by both LLM and humans |


---


---


---

## See also

Prev : [`QueryAnalyst` Orchestrator](query_analyst.md) | Next : [`TaskAnalyzer`](task_analyzer.md)


## Related

- [InformationDigestionLoop + mandatory digest call](../loops/information_digestion_loop.md)
- [DigestedInformation output](../state/digested_information.md)
- [ContextEnhancedQuery from QueryAnalyst](../state/mode_decision.md)
- [Spawned by TinyCUA in worker mode](tinycua.md)
- [enhanced_context_retrieval + digest_information tools](../constants/tools.md)
