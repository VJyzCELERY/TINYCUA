"""Tests for the Milestone 8 Stream B runtime compaction trigger.

Verifies `_maybe_compact` fires when the last input-token count exceeds
the threshold fraction of the bound model's max_context, and that it
compacts the session_context (keeping the most recent entries). Also
covers the lazy LLM-call wiring on SimpleCompaction.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock


from tinycua.compaction.simple import SimpleCompaction
from tinycua.config.session_config import SessionConfig
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session
from tinycua.models.session_context_entry import SessionContextEntry


def _make_loop(session: Session) -> TinyCUALoop:
    return TinyCUALoop(root_session=session, queue=NodeQueue(), session_config=session.session_config)


def _make_agent(max_context: int = 1000) -> SimpleNamespace:
    model = SimpleNamespace(max_context=max_context)
    config = SimpleNamespace(llm_model=model)
    return SimpleNamespace(config=config)


def _entry(content: str, segment: str = "output") -> SessionContextEntry:
    return SessionContextEntry(content=content, segment=segment)


async def test_maybe_compact_noop_without_strategy():
    """No compaction strategy → no-op, session_context untouched."""
    session = Session(session_config=SessionConfig(compaction_strategy=None))
    session._last_input_tokens = 900
    session.session_context = [_entry("a"), _entry("b")]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    await loop._maybe_compact(node, agent)
    assert len(session.session_context) == 2


async def test_maybe_compact_noop_without_token_data():
    """No prior token data (chicken-and-egg) → no-op."""
    strategy = SimpleCompaction()
    session = Session(
        session_config=SessionConfig(compaction_strategy=strategy, compaction_threshold=0.5)
    )
    session._last_input_tokens = 0
    session.session_context = [_entry("a"), _entry("b"), _entry("c"), _entry("d")]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    await loop._maybe_compact(node, agent)
    assert len(session.session_context) == 4


async def test_maybe_compact_noop_below_threshold():
    """Last tokens below threshold → no-op."""
    strategy = SimpleCompaction()
    strategy.compact = AsyncMock(return_value={"role": "assistant", "content": "sum"})
    session = Session(
        session_config=SessionConfig(compaction_strategy=strategy, compaction_threshold=0.7)
    )
    session._last_input_tokens = 500  # 500 < 0.7 * 1000 = 700
    session.session_context = [_entry("a"), _entry("b"), _entry("c"), _entry("d")]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    await loop._maybe_compact(node, agent)
    strategy.compact.assert_not_called()
    assert len(session.session_context) == 4


async def test_maybe_compact_fires_above_threshold():
    """Last tokens above threshold → compacts, keeps recent entries."""
    strategy = SimpleCompaction()
    strategy.compact = AsyncMock(return_value={"role": "assistant", "content": "sum"})
    session = Session(
        session_config=SessionConfig(
            compaction_strategy=strategy,
            compaction_threshold=0.5,
            compaction_keep_recent=2,
        )
    )
    session._last_input_tokens = 800  # 800 > 0.5 * 1000 = 500
    session.session_context = [
        _entry("old1"),
        _entry("old2"),
        _entry("old3"),
        _entry("recent1"),
        _entry("recent2"),
    ]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    await loop._maybe_compact(node, agent)
    strategy.compact.assert_awaited_once()
    # 5 entries → keep 2 → compact 3 → result: 1 summary + 2 recent = 3
    assert len(session.session_context) == 3


async def test_maybe_compact_noop_when_entries_le_keep_recent():
    """Fewer entries than keep_recent → no-op."""
    strategy = SimpleCompaction()
    strategy.compact = AsyncMock(return_value={"role": "assistant", "content": "sum"})
    session = Session(
        session_config=SessionConfig(
            compaction_strategy=strategy,
            compaction_threshold=0.5,
            compaction_keep_recent=5,
        )
    )
    session._last_input_tokens = 800
    session.session_context = [_entry("a"), _entry("b")]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    await loop._maybe_compact(node, agent)
    strategy.compact.assert_not_called()
    assert len(session.session_context) == 2


async def test_maybe_compact_lazy_wires_llm_call():
    """SimpleCompaction without llm_call gets one wired from the agent."""
    strategy = SimpleCompaction()
    strategy.compact = AsyncMock(return_value={"role": "assistant", "content": "sum"})
    session = Session(
        session_config=SessionConfig(
            compaction_strategy=strategy,
            compaction_threshold=0.5,
            compaction_keep_recent=1,
        )
    )
    session._last_input_tokens = 800
    session.session_context = [_entry("a"), _entry("b"), _entry("c")]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    assert strategy._llm_call is None
    await loop._maybe_compact(node, agent)
    assert strategy._llm_call is not None


async def test_maybe_compact_swallows_compaction_errors():
    """A compaction failure is logged, not raised."""
    strategy = SimpleCompaction()
    strategy.compact = AsyncMock(side_effect=RuntimeError("boom"))
    session = Session(
        session_config=SessionConfig(
            compaction_strategy=strategy,
            compaction_threshold=0.5,
            compaction_keep_recent=1,
        )
    )
    session._last_input_tokens = 800
    session.session_context = [_entry("a"), _entry("b"), _entry("c")]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    # Must not raise.
    await loop._maybe_compact(node, agent)
