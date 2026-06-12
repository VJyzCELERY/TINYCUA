"""Tests for WorkerNode with DigestedInformation."""

from unittest.mock import MagicMock

from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.session import Session


class TestWorkerDigestedInformation:
    """Tests for WorkerNode digested information handling."""

    def test_get_digested_input_returns_digest_when_present(self) -> None:
        """_get_digested_input returns DigestedInformation from session_context."""
        worker = TinyCUAWorkerNode(node_id="w", config=MagicMock())
        session = Session()

        digest = DigestedInformation(
            context_summary="Summary of context",
            key_points=["key1"],
            original_query="test query",
        )
        session.session_context.append({
            "role": "assistant",
            "content": digest,
        })
        worker.session = session

        result = worker._get_digested_input()
        assert result is not None
        assert result.context_summary == "Summary of context"
        assert result.original_query == "test query"
        assert result.key_points == ["key1"]

    def test_get_digested_input_returns_none_when_no_digest(self) -> None:
        """_get_digested_input returns None when no digest in session_context."""
        worker = TinyCUAWorkerNode(node_id="w", config=MagicMock())
        session = Session()
        session.session_context.append({
            "role": "assistant",
            "content": "regular message",
        })
        worker.session = session

        result = worker._get_digested_input()
        assert result is None

    def test_get_digested_input_returns_none_when_no_session(self) -> None:
        """_get_digested_input returns None when session is None."""
        worker = TinyCUAWorkerNode(node_id="w", config=MagicMock())
        worker.session = None

        result = worker._get_digested_input()
        assert result is None

    def test_get_digested_input_returns_most_recent_digest(self) -> None:
        """_get_digested_input returns the most recent digest when multiple exist."""
        worker = TinyCUAWorkerNode(node_id="w", config=MagicMock())
        session = Session()

        digest1 = DigestedInformation(
            context_summary="First digest",
            original_query="query 1",
        )
        digest2 = DigestedInformation(
            context_summary="Second digest",
            original_query="query 2",
            key_points=["point"],
        )

        session.session_context.append({
            "role": "assistant",
            "content": digest1,
        })
        session.session_context.append({
            "role": "assistant",
            "content": "some message",
        })
        session.session_context.append({
            "role": "assistant",
            "content": digest2,
        })
        worker.session = session

        result = worker._get_digested_input()
        assert result is not None
        assert result.context_summary == "Second digest"
        assert result.original_query == "query 2"

    def test_propagate_forwards_digested_information(self) -> None:
        """propagate() includes DigestedInformation for downstream nodes."""
        worker = TinyCUAWorkerNode(node_id="w", config=MagicMock())
        session = Session()
        worker.session = session

        digest = DigestedInformation(
            context_summary="Summary",
            original_query="test",
        )
        worker._current_digest = digest

        worker.propagate()

        # After propagate, session_context should contain the digest
        assert any(
            entry.content is digest
            for entry in session.session_context
        )

    def test_propagate_noop_when_no_digest(self) -> None:
        """propagate() does nothing when _current_digest is None."""
        worker = TinyCUAWorkerNode(node_id="w", config=MagicMock())
        session = Session()
        worker.session = session
        worker._current_digest = None

        initial_len = len(session.session_context)
        worker.propagate()

        assert len(session.session_context) == initial_len

    def test_propagate_noop_when_no_session(self) -> None:
        """propagate() does nothing when session is None."""
        worker = TinyCUAWorkerNode(node_id="w", config=MagicMock())
        worker.session = None
        worker._current_digest = DigestedInformation(original_query="test")

        # Should not raise
        worker.propagate()
