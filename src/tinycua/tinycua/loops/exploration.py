"""ExplorationLoop — precision-oriented exploration using retrieval."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.loop import BaseLoop

from tinycua.state import DigestedInformation

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

__all__ = ["ExplorationLoop", "ExplorationConfig"]


@dataclass
class ExplorationConfig:
    """Configuration for :class:`ExplorationLoop`.

    Attributes:
        max_search_iterations: Maximum search iterations.
        relevance_threshold: Minimum relevance score to include results.
        max_results_per_query: Maximum results per search query.
    """

    max_search_iterations: int = 3
    relevance_threshold: float = 0.6
    max_results_per_query: int = 5


_EXPLORATION_SYSTEM_PROMPT = """\
You are an information digester. Your task is to explore session context \
to find and compile relevant information for a given query.

First, identify information gaps — what information do you need that \
is not already in the query?

Then search for context using the available retrieval tool.

Finally, compile your findings into a structured summary.

Respond with a JSON object containing:
- "context_summary": A compressed summary of relevant context in markdown.
- "key_points": A list of key takeaway points (strings).
- "known_gaps": A list of missing information that was searched for but \
not found (optional, empty list if none).
"""


class ExplorationLoop(BaseLoop):
    """Precision-oriented exploration using an injected retrieval tool.

    Iteratively identifies information gaps, searches session context,
    judges relevance, and compiles :class:`DigestedInformation`.

    Args:
        max_iterations: Maximum iterations (default 5).
        max_search_iterations: Maximum search iterations.
        relevance_threshold: Minimum relevance score (0.0–1.0).
    """

    def __init__(
        self,
        max_iterations: int = 5,
        max_search_iterations: int = 3,
        relevance_threshold: float = 0.6,
    ) -> None:
        super().__init__(max_iterations=max_iterations)
        self.max_search_iterations = max_search_iterations
        self.relevance_threshold = relevance_threshold

    def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        stream: bool = False,
        *,
        context_enhanced_query: str,
        caller: str = "primary_agent",
    ) -> DigestedInformation | AsyncIterator[dict[str, Any]]:
        """Run the exploration loop.

        When ``stream=False`` (default), returns a coroutine that resolves
        to ``DigestedInformation`` — call with ``await``.

        When ``stream=True``, returns an async iterator of SSE event dicts
        — use ``async for`` to consume.

        Args:
            agent: The agent executing the loop.
            messages: Existing conversation messages.
            tools: Available tools (must include retrieval tool).
            stream: When True, yields SSE events.
            context_enhanced_query: The context-enhanced query string.
            caller: Identifier of the calling agent ("primary_agent" or
                "worker").

        Returns:
            A coroutine resolving to ``DigestedInformation`` when
            ``stream=False``, or an async iterator of stream events.
        """
        if stream:
            return self._run_stream_exploration(
                agent, messages, tools, context_enhanced_query,
            )

        retrieval_tool = self._find_retrieval_tool(tools)
        return self._run_sync_exploration(
            agent, retrieval_tool, context_enhanced_query, caller,
        )

    async def _run_sync_exploration(
        self,
        agent: Agent,
        retrieval_tool: Tool,
        context_enhanced_query: str,
        caller: str,
    ) -> DigestedInformation:
        """Execute exploration synchronously."""
        search_results = await self._search_context(
            retrieval_tool, agent, context_enhanced_query,
        )
        relevant = [
            r for r in search_results
            if r.get("relevance", 0) >= self.relevance_threshold
        ]
        return await self._compile_findings(
            agent, context_enhanced_query, caller, relevant,
        )

    def _find_retrieval_tool(self, tools: list[Tool]) -> Tool:
        """Find the first retrieval-capable tool in the tool list."""
        for tool in tools:
            if hasattr(tool, "name") and "retrieval" in tool.name.lower():
                return tool
        raise ValueError(
            "No retrieval tool found in tools list. "
            "ExplorationLoop requires a tool with 'retrieval' in its name.",
        )

    async def _search_context(
        self,
        tool: Tool,
        agent: Agent,
        query: str,
    ) -> list[dict]:
        """Search session context using the retrieval tool."""
        try:
            result = await tool.invoke(query=query)
        except Exception:
            return []

        raw = result if isinstance(result, dict) else {}
        return raw.get("results", [])

    async def _compile_findings(
        self,
        agent: Agent,
        query: str,
        caller: str,
        search_results: list[dict],
    ) -> DigestedInformation:
        """Compile search results into DigestedInformation via LLM."""
        context_text = "\n".join(
            f"- {r.get('content', '')} (relevance: {r.get('relevance', 0.0)})"
            for r in search_results
        ) if search_results else "No relevant context found."

        working: list[dict] = [
            {"role": "system", "content": _EXPLORATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Context-Enhanced Query: {query}\n"
                    f"Caller: {caller}\n\n"
                    f"Search Results:\n{context_text}\n\n"
                    f"Compile your findings as a JSON object."
                ),
            },
        ]

        llm_response: dict = await agent._call_llm(working, [])  # type: ignore[arg-type]
        return self._parse_exploration_response(llm_response)

    def _parse_exploration_response(
        self,
        response: dict,
    ) -> DigestedInformation:
        """Parse the LLM response into ``DigestedInformation``."""
        content = response.get("content", "{}")
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {}

        return DigestedInformation(
            context_summary=data.get(
                "context_summary",
                "Exploration completed — no structured summary available.",
            ),
            key_points=data.get("key_points", []),
            known_gaps=data.get("known_gaps"),
        )

    async def _run_stream_exploration(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        context_enhanced_query: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream exploration events."""
        yield {"type": "response.created"}
        yield {"type": "response.in_progress"}

        working: list[dict] = [
            {"role": "system", "content": _EXPLORATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Context-Enhanced Query: {context_enhanced_query}\n\n"
                    f"Explore and compile findings as a JSON object."
                ),
            },
        ]

        try:
            llm_stream = await agent._call_llm(working, tools, stream=True)  # type: ignore[arg-type]
            async for event in llm_stream:
                if event.get("type") in ("response.completed", "response.failed"):
                    continue
                yield event
        except Exception as e:
            yield {"type": "response.failed", "error": {"message": str(e)}}
            yield {"type": "error", "error": {"message": str(e)}}
            return

        yield {"type": "response.completed", "finish_reason": "completed"}
