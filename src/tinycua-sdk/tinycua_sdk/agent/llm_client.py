"""LLM client ABC — abstract base for all provider clients.

This module defines the canonical ``LLMClient`` abstract base class
with a concrete ``chat()`` method that performs shared validation
and delegates to the abstract ``_chat_impl()``.

Provider-specific client implementations have been moved to
``tinycua_sdk.providers.open_ai``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from tinycua_sdk.agent.events import LLMEvent, LLMResponse, RawSseEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from tinycua_sdk.agent.events import LLMMessage, LLMToolSpec

def _yield_events(
    events: list[LLMEvent],
    raw_event_obj: RawSseEvent | None,
    raw_events: bool,
) -> Iterator[LLMEvent | tuple[LLMEvent | None, RawSseEvent | None]]:
    """Yield canonical events, optionally paired with raw event.

    Pairing rules (applied when ``raw_events=True``):

    - **Raw-only** (no canonical equivalent): ``(None, raw_event)``
    - **Canonical-only** (synthetic event): ``(canonical_event, None)``
    - **One-to-one** (one raw → one canonical): ``(canonical_event, raw_event)``
    - **One-to-many** (one raw → N canonicals): first gets
      ``(canonical, raw)``, subsequent get ``(canonical, None)``

    Args:
        events: List of canonical events from the normalizer.
        raw_event_obj: Raw SSE event object for pairing.
        raw_events: When True, yield ``(canonical, raw)`` tuples.

    Yields:
        Canonical ``LLMEvent`` items, or ``(LLMEvent | None, RawSseEvent | None)``
        tuples when ``raw_events=True``.
    """
    if not events and raw_events:
        yield (None, raw_event_obj)
    else:
        for i, event in enumerate(events):
            if raw_events:
                yield (event, raw_event_obj if i == 0 else None)
            else:
                yield event


class LLMClient(ABC):
    """Abstract base for LLM API clients with canonical event contract.

    Subclasses must implement ``_chat_impl()`` and ``close()``.
    The concrete ``chat()`` method validates shared constraints
    (e.g. ``raw_events=True`` requires ``stream=True``) then delegates
    to ``_chat_impl()``.

    Tool-call state machine (canonical event flow)::

        tool_call.started  →  tool_call.arguments.delta*  →  tool_call.arguments.done  →  tool_call.ready

    """

    @abstractmethod
    async def _chat_impl(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        stream: bool = False,
        raw_events: bool = False,
    ) -> (
        LLMResponse
        | AsyncIterator[LLMEvent]
        | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]
    ):
        """Provider-specific chat implementation.

        Args:
            messages: Canonical message list.
            tools: Optional list of tool specs.
            stream: When True, return an async iterator of stream events.
            raw_events: When True *and* stream=True, yield ``(canonical, raw)``
                tuples instead of bare ``LLMEvent`` items. Providers that
                do not support raw events ignore this flag.

        Returns:
            Non-streaming: ``LLMResponse``.
            Streaming with ``raw_events=False``: ``AsyncIterator[LLMEvent]``.
            Streaming with ``raw_events=True``: ``AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]``.
        """

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        *,
        stream: bool = False,
        raw_events: bool = False,
    ) -> (
        LLMResponse
        | AsyncIterator[LLMEvent]
        | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]
    ):
        """Send a chat request with shared validation.

        Validates that ``raw_events=True`` requires ``stream=True``,
        then delegates to ``_chat_impl()``.

        .. note::
            When ``raw_events=True``, the yielded ``(canonical, raw)`` tuples
            follow these pairing rules:

            - **Raw-only** (no canonical equivalent): ``(None, raw_event)``
            - **Canonical-only** (synthetic event): ``(canonical_event, None)``
            - **One-to-one**: ``(canonical_event, raw_event)``
            - **One-to-many**: first gets ``(canonical, raw)``, subsequent
              get ``(canonical, None)``

            Consumers MUST handle ``None`` in either slot.

        Args:
            messages: Canonical message list.
            tools: Optional list of tool specs.
            stream: When True, return an async iterator of stream events.
            raw_events: When True *and* stream=True, yield ``(canonical, raw)``
                tuples from ``_chat_impl()``.

        Returns:
            Non-streaming: ``LLMResponse``.
            Streaming: ``AsyncIterator[LLMEvent]`` or paired tuples.
        """
        if raw_events and not stream:
            msg = "raw_events=True requires stream=True"
            raise ValueError(msg)
        return await self._chat_impl(messages, tools, stream=stream, raw_events=raw_events)

    @abstractmethod
    async def close(self) -> None:
        """Close and release any resources held by the client."""


__all__ = ["LLMClient"]
