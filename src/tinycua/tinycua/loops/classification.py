"""ClassificationLoop — fast context scan + score-based mode classification."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.loop import BaseLoop

from tinycua.state import ContextEnhancedQuery, ModeDecision

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

__all__ = ["ClassificationLoop", "ClassificationConfig"]


@dataclass
class ClassificationConfig:
    """Configuration for :class:`ClassificationLoop`.

    Attributes:
        rubric_dimensions: List of dimensions to evaluate during
            classification (e.g., complexity, context_dependency).
        confidence_threshold: Minimum confidence to avoid ``uncertain`` mode.
        max_context_tokens: Maximum tokens for session context truncation.
    """

    rubric_dimensions: list[str] = field(
        default_factory=lambda: ["complexity", "context_dependency"],
    )
    confidence_threshold: float = 0.7
    max_context_tokens: int = 4000


_CLASSIFICATION_SYSTEM_PROMPT = """\
You are a query classification agent. Your job is to analyze a user query \
along with session context and chat history, then produce a structured \
classification.

Evaluate the query along these dimensions:
- {rubric}

Based on your analysis, determine the appropriate mode:
- **primary_agent**: The query can be answered with available context and tools.
- **worker**: The query requires deeper investigation or task execution.
- **uncertain**: You cannot determine the appropriate mode.

Respond with a JSON object containing:
- "mode": one of "primary_agent", "worker", "uncertain"
- "score": float between 0.0 and 1.0 indicating confidence in mode choice
- "confidence": float between 0.0 and 1.0 for overall classification confidence
- "reasons": list of strings explaining the classification
- "enhanced_query": the user query enhanced with relevant session context
"""


class ClassificationLoop(BaseLoop):
    """Fast, high-level context scan + score-based mode classification.

    Produces ``(ContextEnhancedQuery, ModeDecision)`` from a user query,
    session context, and chat history.

    This loop performs a single LLM call — it is a fast, high-level pass
    that does NOT perform deep retrieval.

    Args:
        max_iterations: Maximum iterations (default 5, unused in single-pass).
        rubric_dimensions: Dimensions for classification rubric.
        confidence_threshold: Minimum confidence threshold.
    """

    def __init__(
        self,
        max_iterations: int = 5,
        rubric_dimensions: list[str] | None = None,
        confidence_threshold: float = 0.7,
    ) -> None:
        super().__init__(max_iterations=max_iterations)
        self.rubric_dimensions = rubric_dimensions or [
            "complexity",
            "context_dependency",
        ]
        self.confidence_threshold = confidence_threshold

    def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        stream: bool = False,
        *,
        user_query: str,
        session_context: str,
        chat_history: list[dict],
    ) -> tuple[ContextEnhancedQuery, ModeDecision] | AsyncIterator[dict[str, Any]]:
        """Run the classification loop.

        When ``stream=False`` (default), returns a coroutine that resolves
        to ``(ContextEnhancedQuery, ModeDecision)`` — call with ``await``.

        When ``stream=True``, returns an async iterator of SSE event dicts
        — use ``async for`` to consume.

        Args:
            agent: The agent executing the loop.
            messages: Existing conversation messages.
            tools: Available tools (not used by classification).
            stream: When True, yields SSE events instead of returning a tuple.
            user_query: The user's raw query string.
            session_context: High-level session context string.
            chat_history: Previous chat messages.

        Returns:
            A ``coroutine`` that resolves to ``(ContextEnhancedQuery,
            ModeDecision)`` when ``stream=False``, or an async iterator of
            stream events when ``stream=True``.
        """
        rubric_str = ", ".join(self.rubric_dimensions)
        system_prompt = _CLASSIFICATION_SYSTEM_PROMPT.format(rubric=rubric_str)

        working: list[dict] = [
            {"role": "system", "content": system_prompt},
        ]
        if chat_history:
            working.extend(chat_history[-10:])

        context_section = ""
        if session_context:
            context_section = f"\nSession Context:\n{session_context}\n"
        user_msg = (
            f"User Query: {user_query}\n"
            f"{context_section}"
            f"\nProvide your classification as a JSON object."
        )
        working.append({"role": "user", "content": user_msg})

        if stream:
            return self._run_stream_classification(agent, working, tools)

        return self._run_sync_classification(agent, working, tools, user_query)

    async def _run_sync_classification(
        self,
        agent: Agent,
        working: list[dict],
        tools: list[Tool],
        user_query: str,
    ) -> tuple[ContextEnhancedQuery, ModeDecision]:
        """Execute the classification synchronously (single LLM call)."""
        llm_response: dict = await agent._call_llm(working, tools)  # type: ignore[arg-type]
        return self._parse_classification_response(llm_response, user_query)

    def _parse_classification_response(
        self,
        response: dict,
        user_query: str,
    ) -> tuple[ContextEnhancedQuery, ModeDecision]:
        """Parse the LLM response into ``(ContextEnhancedQuery, ModeDecision)``."""
        content = response.get("content", "{}")
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {}

        mode = data.get("mode", "primary_agent")
        score = float(data.get("score", 0.5))
        confidence = float(data.get("confidence", 0.5))
        reasons = data.get("reasons", ["Classification completed"])
        enhanced_text = data.get("enhanced_query", user_query)

        enhanced_query = ContextEnhancedQuery(enhanced_query=enhanced_text)
        mode_decision = ModeDecision(
            mode=mode,
            score=max(0.0, min(1.0, score)),
            confidence=max(0.0, min(1.0, confidence)),
            reasons=reasons,
        )
        return enhanced_query, mode_decision

    async def _run_stream_classification(
        self,
        agent: Agent,
        working: list[dict],
        tools: list[Tool],
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream classification events."""
        yield {"type": "response.created"}

        try:
            llm_stream = await agent._call_llm(working, tools, stream=True)  # type: ignore[arg-type]
            async for event in llm_stream:
                yield event
        except Exception as e:
            yield {"type": "response.failed", "error": {"message": str(e)}}
            yield {"type": "error", "error": {"message": str(e)}}
            return

        yield {"type": "response.completed", "finish_reason": "completed"}
