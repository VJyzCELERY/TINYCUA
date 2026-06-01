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

InformationDigester uses exactly two tools, both defined in
[`tools/digester.md`](../tools/digester.md):

| Tool | Purpose | Required? |
|------|---------|-----------|
| `enhanced_context_retrieval` | Search the cached full context via internal agent | No |
| `digest_information` | Produce structured `DigestedInformation` output | **Yes** — at least 1 call |

**Factory:** `create_enhanced_context_retrieval(cache_path, model) -> Tool` — spawns an
internal agent with `read_context_cache` (grep + offset/limit, never loads full file).
**Output:** `digest_information` uses `DIGEST_OUTPUT_PREFIX` prefix so the orchestrator
can distinguish it from retrieval results in the event stream.

### Tool wiring in `run()`

```python
cache_path = self._write_context_cache()
tools = [
    create_enhanced_context_retrieval(cache_path=cache_path, model=self.config.model),
    digest_information,
    *self.config.extra_tools,
]
```

## Output Parsing

Unlike other orchestrators that parse the agent's final text response, InformationDigester
extracts `DigestedInformation` from the `digest_information` tool call result:

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

**Key points:**
- Output comes from a tool call, NOT from parsing `"".join(text_parts)` → JSON
- `DIGEST_OUTPUT_PREFIX` discriminates from `enhanced_context_retrieval` results
- Reversed iteration: last `digest_information` call wins (subsequent calls replace)

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
            loop = InformationDigestionLoop(
                state=self.state,
                max_iterations=self.config.max_iterations_override,
            )
            agent = Agent(
                name=self.config.name,
                instructions=instructions,
                llm_model=self.config.model,
                tools=tools,
                loop=loop,
            )

            # 6. Stream with retry — probe for digest_information tool call
            first_response_text: str | None = None
            all_events: list[dict] = []
            max_retries = 3

            for attempt in range(1, max_retries + 1):
                current_query = (
                    query if attempt == 1
                    else "Call digest_information with your findings."
                )

                text_parts: list[str] = []
                async for event in agent.run(query=current_query, stream=True):
                    all_events.append(event)
                    if event["type"] == "response.output_text.delta":
                        text_parts.append(event["delta"])
                    yield event

                response_text = "".join(text_parts)
                if first_response_text is None:
                    first_response_text = response_text

                # Probe for digest_information
                digested = self._parse_digested_output(all_events)
                if digested is not None:
                    # Success — record to both histories
                    self.session.append_assistant(
                        content=response_text,
                        metadata={
                            "orchestrator": "information_digester",
                            "agent_name": self.config.name,
                        },
                    )
                    self.state.digested_information = digested
                    self.state.last_result = digested.to_dict()
                    return

                # Retry: record to chat_history only
                if attempt < max_retries:
                    self.session.chat_history.append(ChatRecord(
                        id=str(uuid4()),
                        type="agent",
                        metadata={
                            "orchestrator": "information_digester",
                            "agent_name": self.config.name,
                        },
                        content={"text": response_text or "(no response)"},
                    ))

            # Max retries exhausted
            self.state.digested_information = None
            self.state.last_result = None

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
| Mandatory digest via retry | Orchestrator probes `digest_information` tool calls; retries up to 3x | Same pattern as QueryAnalyst/TaskAssessor; loop stays simple |
| Retry responses → chat_history only | Direct `chat_history.append(ChatRecord(...))` on retry | Internal retry nudges don't pollute session_context |
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
- [enhanced_context_retrieval + digest_information tools](../tools/digester.md)
