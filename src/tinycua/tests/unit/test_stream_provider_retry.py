"""FR-6: stream-path provider-error retry.

The stream path (`_stream_llm_node_events` → `_collect_stream_events`)
bypassed the FR-086 provider-error retry that the sync path had. A single
SSE stream drop from LM Studio killed the process. FR-6 restructures the
except block to force-compact, clear partial state, and retry up to
``_MAX_PROVIDER_RETRIES`` times.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tinycua.compaction.simple import SimpleCompaction
from tinycua.config.session_config import SessionConfig
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops._loop_constants import _MAX_PROVIDER_RETRIES
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session
from tinycua.models.session_context_entry import SessionContextEntry


def _entry(content: str, segment: str = "output") -> SessionContextEntry:
    return SessionContextEntry(content=content, segment=segment)


def _make_loop(session: Session) -> TinyCUALoop:
    return TinyCUALoop(
        root_session=session,
        queue=NodeQueue(),
        session_config=session.session_config,
    )


def _make_agent(max_context: int = 1000) -> SimpleNamespace:
    model = SimpleNamespace(max_context=max_context)
    config = SimpleNamespace(llm_model=model)
    return SimpleNamespace(config=config)


def _make_node(node_id: str = "test_node", session: Session | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        node_id=node_id,
        session=session,
        is_terminal=False,
        config=SimpleNamespace(
            stream_policy=SimpleNamespace(emit_internal_events=False),
            retry_policy=SimpleNamespace(max_attempts=1),
        ),
    )


class TestStreamProviderErrorRetry:
    """FR-6: stream-path catches provider errors and retries with compaction."""

    async def test_stream_provider_error_retries_then_succeeds(self):
        """Provider error on first call → force-compact → retry → succeeds."""
        session = Session(
            session_config=SessionConfig(
                compaction_strategy=SimpleCompaction(),
                compaction_keep_recent=1,
            )
        )
        session._last_input_tokens = 0
        session.session_context = [_entry("a"), _entry("b"), _entry("c")]
        loop = _make_loop(session)
        agent = _make_agent()
        node = _make_node(session=session)

        call_count = 0

        async def fake_collect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("stream dropped")
            # Second call: yield a completion event.
            yield {"type": "response.completed", "finish_reason": "stop"}

        # Patch _collect_stream_events to raise then succeed.
        loop._collect_stream_events = fake_collect

        # Patch _finalize_streamed_node to return valid result.
        async def fake_finalize(*args, **kwargs):
            return ("ok", ValidationResult(is_valid=True, errors=[]), LLMResult(content="ok"))
        loop._finalize_streamed_node = fake_finalize

        # Patch _stream_valid_node_completion to yield nothing (just return).
        async def fake_valid_completion(*args, **kwargs):
            return
            yield  # never reached — makes it an async generator
        loop._stream_valid_node_completion = fake_valid_completion

        # Patch _messages_with_retry_prompt (called by the retry loop).
        loop._messages_with_retry_prompt = lambda base, feedback, msg: list(base)
        # Patch _force_compact (the core of FR-6).
        loop._force_compact = AsyncMock()

        events = []
        async for event in loop._stream_llm_node_events(
            node, agent, [], [], None,
            None, emit_lifecycle=False, include_meta=False, final_only=True,
            node_type="ProcessNode", attempt=1,
        ):
            events.append(event)

        # Verify retry happened: _collect_stream_events called twice.
        assert call_count == 2, f"expected 2 calls, got {call_count}"
        # Verify force_compact was called (the retry mechanism).
        assert loop._force_compact.called, "_force_compact must be called on retry"

    async def test_stream_provider_error_exhausts_after_max_retries(self):
        """Provider error on every call → re-raises after _MAX_PROVIDER_RETRIES+1."""
        session = Session(
            session_config=SessionConfig(
                compaction_strategy=SimpleCompaction(),
                compaction_keep_recent=1,
            )
        )
        session._last_input_tokens = 0
        session.session_context = [_entry("a"), _entry("b"), _entry("c")]
        loop = _make_loop(session)
        agent = _make_agent()
        node = _make_node(session=session)

        call_count = 0

        async def always_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("stream dropped")
            yield  # never reached — makes it an async generator

        loop._collect_stream_events = always_fail
        loop._force_compact = AsyncMock()
        loop._messages_with_retry_prompt = lambda base, feedback, msg: list(base)

        # After _MAX_PROVIDER_RETRIES retries, the exception should re-raise.
        with pytest.raises(RuntimeError, match="stream dropped"):
            async for _ in loop._stream_llm_node_events(
                node, agent, [], [], None,
                None, emit_lifecycle=False, include_meta=False, final_only=True,
                node_type="ProcessNode", attempt=1,
            ):
                pass

        # _MAX_PROVIDER_RETRIES + 1 initial call = total attempts.
        assert call_count == _MAX_PROVIDER_RETRIES + 1

    async def test_stream_cancelled_error_not_retried(self):
        """asyncio.CancelledError is re-raised immediately without retry."""
        session = Session(
            session_config=SessionConfig(
                compaction_strategy=SimpleCompaction(),
                compaction_keep_recent=1,
            )
        )
        session._last_input_tokens = 0
        session.session_context = [_entry("a"), _entry("b"), _entry("c")]
        loop = _make_loop(session)
        agent = _make_agent()
        node = _make_node(session=session)

        call_count = 0

        async def fail_with_cancel(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise asyncio.CancelledError()
            yield  # never reached — makes it an async generator

        loop._collect_stream_events = fail_with_cancel
        loop._force_compact = AsyncMock()
        loop._messages_with_retry_prompt = lambda base, feedback, msg: list(base)

        with pytest.raises(asyncio.CancelledError):
            async for _ in loop._stream_llm_node_events(
                node, agent, [], [], None,
                None, emit_lifecycle=False, include_meta=False, final_only=True,
                node_type="ProcessNode", attempt=1,
            ):
                pass

        # CancelledError must NOT trigger retry — only 1 call.
        assert call_count == 1
        assert not loop._force_compact.called