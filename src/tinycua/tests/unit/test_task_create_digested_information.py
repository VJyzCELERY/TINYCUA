"""Tests for TaskCreateNode with DigestedInformation."""

from unittest.mock import MagicMock

from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session


def _make_config() -> MagicMock:
    """Create a properly configured mock config for TaskCreateNode."""
    config = MagicMock()
    config.custom_instruction_append = ""
    config.custom_retry_append = ""
    config.message_policy.include_session_context = True
    config.message_policy.include_chat_history = False
    return config


class TestTaskCreateDigestedInformation:
    """Tests for TaskCreateNode digested information handling."""

    def test_build_messages_includes_digested_context(self) -> None:
        """build_messages() includes DigestedInformation from propagate() output."""
        config = _make_config()
        node = TinyCUATaskCreateNode(node_id="tc", config=config)
        session = Session()

        digest = DigestedInformation(
            context_summary="Test summary",
            key_points=["key1", "key2"],
            original_query="test query",
        )
        session.session_context.append({
            "role": "assistant",
            "content": digest,
        })
        node.session = session

        input_data = NodeInput(
            input_type="task_creation",
            messages=[{"role": "user", "content": "test query"}],
        )

        messages = node.build_messages(session, input_data)

        # Should contain digest context in the messages
        # Convert content to string for checking (may be DigestedInformation object)
        messages_str = " ".join(
            str(m.get("content", "")) for m in messages
        )
        assert "Test summary" in messages_str

    def test_build_messages_falls_back_to_raw_query(self) -> None:
        """build_messages() falls back to raw user query when no digest."""
        config = _make_config()
        node = TinyCUATaskCreateNode(node_id="tc", config=config)
        session = Session()

        # No digest in session_context
        session.session_context.append({
            "role": "assistant",
            "content": "some regular message",
        })
        node.session = session

        input_data = NodeInput(
            input_type="task_creation",
            messages=[{"role": "user", "content": "raw query"}],
        )

        messages = node.build_messages(session, input_data)

        # Should contain the raw query
        messages_str = " ".join(m.get("content", "") for m in messages)
        assert "raw query" in messages_str

    def test_build_messages_original_query_preserved(self) -> None:
        """build_messages() preserves original_query from digest."""
        config = _make_config()
        node = TinyCUATaskCreateNode(node_id="tc", config=config)
        session = Session()

        digest = DigestedInformation(
            context_summary="Summary",
            original_query="original user request",
        )
        session.session_context.append({
            "role": "assistant",
            "content": digest,
        })
        node.session = session

        input_data = NodeInput(
            input_type="task_creation",
            messages=[{"role": "user", "content": "original user request"}],
        )

        messages = node.build_messages(session, input_data)

        content = " ".join(
            str(m.get("content", "")) for m in messages
        )
        assert "original user request" in content

    def test_build_messages_with_digest_has_enhanced_context(self) -> None:
        """build_messages() includes enhanced context from digest key_points."""
        config = _make_config()
        node = TinyCUATaskCreateNode(node_id="tc", config=config)
        session = Session()

        digest = DigestedInformation(
            context_summary="Summary of requirements",
            key_points=["Need authentication", "Support OAuth2"],
            advisory_instructions=["Use JWT tokens"],
            constraints=["Must be stateless"],
            original_query="Implement auth system",
        )
        session.session_context.append({
            "role": "assistant",
            "content": digest,
        })
        node.session = session

        input_data = NodeInput(
            input_type="task_creation",
            messages=[{"role": "user", "content": "Implement auth system"}],
        )

        messages = node.build_messages(session, input_data)

        content = " ".join(str(m.get("content", "")) for m in messages)
        assert "Need authentication" in content
        assert "Support OAuth2" in content
        assert "Use JWT tokens" in content
        assert "Must be stateless" in content
        assert "Summary of requirements" in content
