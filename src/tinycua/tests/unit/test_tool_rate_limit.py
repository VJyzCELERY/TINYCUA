"""Tests for the per-tool rate-limit gate in TinyCUALoop.

Verifies ``_await_tool_rate_limit`` enforces a minimum interval between
calls to rate-limited tools (e.g. ``web_search``) and is a no-op for
unlisted tools. Uses a stub loop with a lowered interval to keep the
test fast.
"""

from __future__ import annotations

import time

import pytest

from tinycua.config.session_config import SessionConfig
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session


@pytest.fixture
def loop_with_fast_rate_limit(monkeypatch):
    """Patch the web_search interval to 0.3s for fast tests."""
    monkeypatch.setattr(
        "tinycua.loops.tinycua_loop._TOOL_RATE_LIMITS",
        {"web_search": (0.3, 0.0)},
    )
    session = Session(session_config=SessionConfig())
    return TinyCUALoop(
        root_session=session, queue=NodeQueue(), session_config=session.session_config
    )


async def test_rate_limit_noop_for_unlisted_tool(loop_with_fast_rate_limit):
    """Unlisted tools pass through with no sleep."""
    loop = loop_with_fast_rate_limit
    start = time.monotonic()
    await loop._await_tool_rate_limit("read_file")
    elapsed = time.monotonic() - start
    assert elapsed < 0.05  # no waiting


async def test_rate_limit_first_call_no_wait(loop_with_fast_rate_limit):
    """First call to a rate-limited tool doesn't wait (last_ts=0)."""
    loop = loop_with_fast_rate_limit
    start = time.monotonic()
    await loop._await_tool_rate_limit("web_search")
    elapsed = time.monotonic() - start
    assert elapsed < 0.05  # first call passes straight through


async def test_rate_limit_second_call_waits(loop_with_fast_rate_limit):
    """Second call within the interval waits for the gap to elapse."""
    loop = loop_with_fast_rate_limit
    await loop._await_tool_rate_limit("web_search")  # first call: no wait
    start = time.monotonic()
    await loop._await_tool_rate_limit("web_search")  # second call: waits ~0.3s
    elapsed = time.monotonic() - start
    assert elapsed >= 0.25  # waited at least the interval (allow slack)


async def test_rate_limit_third_after_gap_no_wait(loop_with_fast_rate_limit):
    """Call after the interval has elapsed doesn't wait."""
    loop = loop_with_fast_rate_limit
    await loop._await_tool_rate_limit("web_search")
    await loop._await_tool_rate_limit("web_search")  # waits 0.3s
    # Sleep past the interval so the next call's last_ts is stale.
    import asyncio

    await asyncio.sleep(0.35)
    start = time.monotonic()
    await loop._await_tool_rate_limit("web_search")
    elapsed = time.monotonic() - start
    assert elapsed < 0.05
