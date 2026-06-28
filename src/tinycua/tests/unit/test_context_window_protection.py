"""Unit tests for FR-082..FR-086: context window protection hotfix (Milestone 9).

Covers the five fixes that compose to bound the prompt to the real served
context window:
  - FR-082: compaction wired into the CLI run path
  - FR-083: max_context_messages enforced at message-build time
  - FR-084: server probe for real max_context + --max-context override
  - FR-085: continuous compaction monitoring + INFO-level logs
  - FR-086: catch-and-retry on provider errors (force-compact + retry)
"""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tinycua.compaction.simple import SimpleCompaction
from tinycua.config.session_config import SessionConfig
from tinycua.loops.node import build_messages_with_dedupe
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session
from tinycua.models.session_context_entry import SessionContextEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(content: str, segment: str = "output") -> SessionContextEntry:
    """Build a minimal SessionContextEntry for tests."""
    return SessionContextEntry(content=content, segment=segment)


def _make_loop(session: Session) -> TinyCUALoop:
    """Build a TinyCUALoop bound to the given session."""
    return TinyCUALoop(
        root_session=session,
        queue=NodeQueue(),
        session_config=session.session_config,
    )


def _make_agent(max_context: int = 1000) -> SimpleNamespace:
    """Build a minimal agent stub with a max_context-bearing model."""
    model = SimpleNamespace(max_context=max_context)
    config = SimpleNamespace(llm_model=model)
    return SimpleNamespace(config=config)


# ---------------------------------------------------------------------------
# FR-082: compaction wired into the CLI run path
# ---------------------------------------------------------------------------


def test_fr082_build_run_agent_sets_compaction_strategy(tmp_path: Path) -> None:
    """FR-082: _build_run_agent wires SimpleCompaction into the SessionConfig."""
    from tinycua.cli.run import _build_run_agent

    config = {
        "base_url": "http://localhost:1234/v1",
        "api_key": "test-key",
        "model": "test-model",
        "provider_type": "openai-chat-completions",
    }
    agent = _build_run_agent(
        config,
        workspace=tmp_path,
        artifact_dir=None,
        worker_effort="medium",
        no_tool_audit=False,
        allow_open_question=False,
        replan_threshold=5,
        log_path=None,
    )
    sc = agent.loop.session_config
    assert sc is not None
    assert isinstance(sc.compaction_strategy, SimpleCompaction), (
        "CLI run path must set compaction_strategy=SimpleCompaction() (FR-082)"
    )


# ---------------------------------------------------------------------------
# FR-083: max_context_messages enforced at message-build time
# ---------------------------------------------------------------------------


def test_fr083_cap_bounds_prompt_to_last_n() -> None:
    """FR-083: prompt-bound messages bounded to last max_context_messages."""
    session = Session(session_config=SessionConfig(max_context_messages=3))
    for i in range(10):
        session.session_context.append(_entry(f"entry {i}"))
    messages = build_messages_with_dedupe(session)
    assert len(messages) <= 3, "prompt must be bounded to last max_context_messages"
    # The last 3 entries are the ones kept
    contents = [m["content"] for m in messages]
    assert "entry 9" in contents
    assert "entry 8" in contents
    assert "entry 7" in contents
    # entry 0-6 dropped from prompt
    assert "entry 0" not in contents


def test_fr083_audit_trail_intact() -> None:
    """FR-083: session_context list is never mutated by the cap."""
    session = Session(session_config=SessionConfig(max_context_messages=3))
    for i in range(10):
        session.session_context.append(_entry(f"entry {i}"))
    build_messages_with_dedupe(session)
    assert len(session.session_context) == 10, "audit trail must stay intact"


def test_fr083_none_means_unlimited() -> None:
    """FR-083: max_context_messages=None disables the cap."""
    session = Session(session_config=SessionConfig(max_context_messages=None))
    for i in range(10):
        session.session_context.append(_entry(f"entry {i}"))
    messages = build_messages_with_dedupe(session)
    assert len(messages) == 10, "None must mean unlimited (no cap)"


def test_fr083_under_cap_unchanged() -> None:
    """FR-083: when entries <= cap, all are sent (no truncation)."""
    session = Session(session_config=SessionConfig(max_context_messages=100))
    for i in range(5):
        session.session_context.append(_entry(f"entry {i}"))
    messages = build_messages_with_dedupe(session)
    assert len(messages) == 5


# ---------------------------------------------------------------------------
# FR-084: server probe for real max_context
# ---------------------------------------------------------------------------


async def test_fr084_probe_returns_context_length() -> None:
    """FR-084: resolve_max_context returns the server-reported context_length."""
    from tinycua.cli.model_probe import resolve_max_context

    mock_model = MagicMock()
    mock_model.id = "qwen3.5-9b"
    mock_model.context_length = 32768
    mock_list = MagicMock()
    mock_list.data = [mock_model]
    with patch("tinycua.cli.model_probe.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(return_value=mock_list)
        mock_client.close = AsyncMock()
        mock_client_cls.return_value = mock_client
        result = await resolve_max_context(
            "http://localhost:1234/v1", "key", "qwen3.5-9b", fallback=128000
        )
    assert result == 32768


async def test_fr084_probe_error_falls_back() -> None:
    """FR-084: resolve_max_context falls back on network error."""
    from tinycua.cli.model_probe import resolve_max_context

    with patch("tinycua.cli.model_probe.AsyncOpenAI", side_effect=Exception("network")):
        result = await resolve_max_context(
            "http://localhost:1234/v1", "key", "m", fallback=128000
        )
    assert result == 128000


async def test_fr084_probe_missing_field_falls_back() -> None:
    """FR-084: resolve_max_context falls back when context_length is absent."""
    from tinycua.cli.model_probe import resolve_max_context

    mock_model = MagicMock()
    mock_model.id = "gpt-4o"
    mock_model.context_length = None
    mock_list = MagicMock()
    mock_list.data = [mock_model]
    with patch("tinycua.cli.model_probe.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(return_value=mock_list)
        mock_client.close = AsyncMock()
        mock_client_cls.return_value = mock_client
        result = await resolve_max_context(
            "http://localhost:1234/v1", "key", "gpt-4o", fallback=128000
        )
    assert result == 128000


async def test_fr084_probe_no_models_falls_back() -> None:
    """FR-084: resolve_max_context falls back when the models list is empty."""
    from tinycua.cli.model_probe import resolve_max_context

    mock_list = MagicMock()
    mock_list.data = []
    with patch("tinycua.cli.model_probe.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(return_value=mock_list)
        mock_client.close = AsyncMock()
        mock_client_cls.return_value = mock_client
        result = await resolve_max_context(
            "http://localhost:1234/v1", "key", "m", fallback=128000
        )
    assert result == 128000


def test_fr084_build_language_model_accepts_max_context() -> None:
    """FR-084: build_language_model passes max_context to LanguageModel."""
    from tinycua.cli.config import build_language_model

    config = {
        "base_url": "http://localhost:1234/v1",
        "api_key": "test-key",
        "model": "test-model",
        "provider_type": "openai-chat-completions",
    }
    lm = build_language_model(config, max_context=4096)
    assert lm.max_context == 4096


def test_fr084_build_language_model_default_when_no_max_context() -> None:
    """FR-084: build_language_model keeps SDK default when max_context is None."""
    from tinycua.cli.config import build_language_model

    config = {
        "base_url": "http://localhost:1234/v1",
        "api_key": "test-key",
        "model": "test-model",
        "provider_type": "openai-chat-completions",
    }
    lm = build_language_model(config)
    assert lm.max_context == 128000


# ---------------------------------------------------------------------------
# FR-085: continuous compaction monitoring + INFO logs
# ---------------------------------------------------------------------------


def test_fr085_maybe_compact_not_gated_on_attempt_gt_1() -> None:
    """FR-085: _maybe_compact is called at top of attempt loop, not inside 'if attempt > 1'."""
    src = inspect.getsource(TinyCUALoop._call_node_with_retry)
    # Find the _maybe_compact call and verify it's NOT inside an 'if attempt > 1' block.
    # The call site moved to the top of the loop body.
    maybe_compact_idx = src.find("_maybe_compact")
    assert maybe_compact_idx != -1, "_maybe_compact must be called in _call_node_with_retry"
    # Check the region immediately before the call for an 'if attempt > 1' gate
    region_before = src[:maybe_compact_idx]
    # The old pattern was:
    #   if attempt > 1:
    #       await self._maybe_compact(node, agent)
    # The new pattern calls it unconditionally at the top of the loop.
    # Assert the call is NOT on a line indented under 'if attempt > 1'.
    # Simplest: find 'if attempt > 1' and check _maybe_compact is not after it
    # at the same or deeper indent within the same block.
    if_idx = region_before.rfind("if attempt > 1")
    if if_idx != -1:
        # If there's an 'if attempt > 1' before the call, the _maybe_compact call
        # must NOT be the body of that if (i.e. there must be other code between
        # the if and the call, OR the call is at a different scope).
        after_if = src[if_idx:maybe_compact_idx]
        # If the only thing between 'if attempt > 1:' and '_maybe_compact' is
        # whitespace/newlines, the call is still gated — fail.
        stripped = after_if.replace("if attempt > 1:", "").strip()
        if stripped.startswith("await self._maybe_compact") or stripped == "":
            pytest.fail(
                "_maybe_compact is still gated behind 'if attempt > 1' (FR-085 violated)"
            )


async def test_fr085_compaction_trigger_logged_at_info(caplog: pytest.LogCaptureFixture) -> None:
    """FR-085: compaction_trigger event is logged at INFO level."""
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
    with caplog.at_level(logging.INFO, logger="tinycua.loops.tinycua_loop"):
        await loop._maybe_compact(node, agent)
    trigger_records = [r for r in caplog.records if "compaction_trigger" in r.getMessage()]
    assert trigger_records, "compaction_trigger must be logged"
    assert trigger_records[0].levelno == logging.INFO, (
        "compaction_trigger must be at INFO level (FR-085)"
    )


async def test_fr085_compaction_failure_logged_at_info(caplog: pytest.LogCaptureFixture) -> None:
    """FR-085: compaction_failed event is logged at INFO level."""
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
    with caplog.at_level(logging.INFO, logger="tinycua.loops.tinycua_loop"):
        await loop._maybe_compact(node, agent)
    fail_records = [r for r in caplog.records if "compaction_failed" in r.getMessage()]
    assert fail_records, "compaction_failed must be logged"
    assert fail_records[0].levelno == logging.INFO, (
        "compaction_failed must be at INFO level (FR-085)"
    )


# ---------------------------------------------------------------------------
# FR-086: catch-and-retry on provider errors
# ---------------------------------------------------------------------------


async def test_fr086_force_compact_bypasses_threshold() -> None:
    """FR-086: _force_compact compacts even when _last_input_tokens is 0."""
    strategy = SimpleCompaction()
    strategy.compact = AsyncMock(return_value={"role": "assistant", "content": "sum"})
    session = Session(
        session_config=SessionConfig(
            compaction_strategy=strategy,
            compaction_keep_recent=1,
        )
    )
    session._last_input_tokens = 0  # no usage data from a failed call
    session.session_context = [_entry("a"), _entry("b"), _entry("c"), _entry("d")]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    await loop._force_compact(node, agent)
    # Force-compact bypasses the threshold check → compacts regardless.
    strategy.compact.assert_awaited_once()
    # 4 entries → keep 1 → compact 3 → result: 1 summary + 1 recent = 2
    assert len(session.session_context) == 2


async def test_fr086_force_compact_noop_without_strategy() -> None:
    """FR-086: _force_compact is a no-op when no compaction strategy is set."""
    session = Session(session_config=SessionConfig(compaction_strategy=None))
    session._last_input_tokens = 0
    session.session_context = [_entry("a"), _entry("b"), _entry("c")]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    await loop._force_compact(node, agent)
    assert len(session.session_context) == 3  # untouched


async def test_fr086_force_compact_noop_when_too_few_entries() -> None:
    """FR-086: _force_compact is a no-op when entries <= keep_recent."""
    strategy = SimpleCompaction()
    strategy.compact = AsyncMock(return_value={"role": "assistant", "content": "sum"})
    session = Session(
        session_config=SessionConfig(
            compaction_strategy=strategy,
            compaction_keep_recent=5,
        )
    )
    session._last_input_tokens = 0
    session.session_context = [_entry("a"), _entry("b")]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    await loop._force_compact(node, agent)
    strategy.compact.assert_not_called()
    assert len(session.session_context) == 2


async def test_fr086_force_compact_logs_at_info(caplog: pytest.LogCaptureFixture) -> None:
    """FR-086: forced_compaction event is logged at INFO level."""
    strategy = SimpleCompaction()
    strategy.compact = AsyncMock(return_value={"role": "assistant", "content": "sum"})
    session = Session(
        session_config=SessionConfig(
            compaction_strategy=strategy,
            compaction_keep_recent=1,
        )
    )
    session._last_input_tokens = 0
    session.session_context = [_entry("a"), _entry("b"), _entry("c")]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    with caplog.at_level(logging.INFO, logger="tinycua.loops.tinycua_loop"):
        await loop._force_compact(node, agent)
    trigger_records = [r for r in caplog.records if "forced_compaction" in r.getMessage()]
    assert trigger_records, "forced_compaction must be logged"
    assert trigger_records[0].levelno == logging.INFO


async def test_fr086_max_provider_retries_constant_exists() -> None:
    """FR-086: _MAX_PROVIDER_RETRIES constant is defined in _loop_constants."""
    from tinycua.loops._loop_constants import _MAX_PROVIDER_RETRIES

    assert isinstance(_MAX_PROVIDER_RETRIES, int)
    assert _MAX_PROVIDER_RETRIES > 0
    assert _MAX_PROVIDER_RETRIES <= 10  # reasonable bound


async def test_fr086_force_compact_swallows_errors(caplog: pytest.LogCaptureFixture) -> None:
    """FR-086: _force_compact catches compaction failures (logged, not raised)."""
    strategy = SimpleCompaction()
    strategy.compact = AsyncMock(side_effect=RuntimeError("compaction LLM failed"))
    session = Session(
        session_config=SessionConfig(
            compaction_strategy=strategy,
            compaction_keep_recent=1,
        )
    )
    session._last_input_tokens = 0
    session.session_context = [_entry("a"), _entry("b"), _entry("c")]
    loop = _make_loop(session)
    agent = _make_agent(max_context=1000)
    node = SimpleNamespace(node_id="x", session=session)
    with caplog.at_level(logging.INFO, logger="tinycua.loops.tinycua_loop"):
        # Must not raise.
        await loop._force_compact(node, agent)
    fail_records = [r for r in caplog.records if "forced_compaction_failed" in r.getMessage()]
    assert fail_records, "forced_compaction_failed must be logged"
