"""Unit tests for ChatRecord model."""

from tinycua.models.chat_record import ChatRecord


def test_chat_record_creation():
    """ChatRecord instantiation with all metadata fields."""
    record = ChatRecord(
        record_id="rec-1",
        role="assistant",
        record_type="node_output",
        content="Hello world",
        visibility="user_visible",
        source_node_id="node-1",
        source_session_id="session-1",
        receiver_node_id="node-2",
        receiver_session_id="session-2",
        origin_record_id="orig-1",
        created_seq=1,
        metadata={"key": "value"},
    )

    assert record.record_id == "rec-1"
    assert record.role == "assistant"
    assert record.record_type == "node_output"
    assert record.content == "Hello world"
    assert record.visibility == "user_visible"
    assert record.source_node_id == "node-1"
    assert record.source_session_id == "session-1"
    assert record.receiver_node_id == "node-2"
    assert record.receiver_session_id == "session-2"
    assert record.origin_record_id == "orig-1"
    assert record.created_seq == 1
    assert record.metadata == {"key": "value"}


def test_chat_record_defaults():
    """ChatRecord with minimal required fields uses defaults."""
    record = ChatRecord(
        record_id="rec-2",
        role="user",
        record_type="propagation",
        content="test content",
        visibility="internal",
        created_seq=1,
    )

    assert record.source_node_id is None
    assert record.source_session_id is None
    assert record.receiver_node_id is None
    assert record.receiver_session_id is None
    assert record.origin_record_id is None
    assert record.metadata == {}


def test_chat_record_serialization():
    """ChatRecord to_dict and from_dict roundtrip."""
    record = ChatRecord(
        record_id="rec-3",
        role="assistant",
        record_type="tool_result",
        content={"tool": "result"},
        visibility="tool_only",
        source_node_id="node-3",
        source_session_id="session-3",
        receiver_node_id="node-4",
        receiver_session_id="session-4",
        origin_record_id="orig-3",
        created_seq=3,
        metadata={"trace": "abc"},
    )

    record_dict = record.to_dict()
    restored = ChatRecord.from_dict(record_dict)

    assert restored.record_id == record.record_id
    assert restored.role == record.role
    assert restored.record_type == record.record_type
    assert restored.content == record.content
    assert restored.visibility == record.visibility
    assert restored.source_node_id == record.source_node_id
    assert restored.source_session_id == record.source_session_id
    assert restored.receiver_node_id == record.receiver_node_id
    assert restored.receiver_session_id == record.receiver_session_id
    assert restored.origin_record_id == record.origin_record_id
    assert restored.created_seq == record.created_seq
    assert restored.metadata == record.metadata


def test_chat_record_auto_id():
    """ChatRecord generates record_id if not provided."""
    record = ChatRecord(
        role="system",
        record_type="propagation",
        content="auto id test",
        visibility="internal",
        created_seq=1,
    )

    assert record.record_id is not None
    assert len(record.record_id) == 32  # uuid4 hex length
