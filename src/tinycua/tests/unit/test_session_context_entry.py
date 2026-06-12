"""Unit tests for SessionContextEntry model."""

from tinycua.models.session_context_entry import SessionContextEntry


def test_session_context_entry_creation():
    """SessionContextEntry instantiation with all fields."""
    entry = SessionContextEntry(
        record_id="entry-1",
        segment="prior",
        content="context content",
        origin_record_id="orig-1",
        source_node_id="node-1",
        source_session_id="session-1",
        created_seq=1,
    )

    assert entry.record_id == "entry-1"
    assert entry.segment == "prior"
    assert entry.content == "context content"
    assert entry.origin_record_id == "orig-1"
    assert entry.source_node_id == "node-1"
    assert entry.source_session_id == "session-1"
    assert entry.created_seq == 1


def test_session_context_entry_defaults():
    """SessionContextEntry with minimal required fields uses defaults."""
    entry = SessionContextEntry(
        record_id="entry-2",
        segment="input",
        content="input content",
        created_seq=2,
    )

    assert entry.origin_record_id is None
    assert entry.source_node_id is None
    assert entry.source_session_id is None


def test_session_context_entry_segment_values():
    """SessionContextEntry supports all three segment values."""
    prior = SessionContextEntry(record_id="p", segment="prior", content="p", created_seq=1)
    inp = SessionContextEntry(record_id="i", segment="input", content="i", created_seq=2)
    out = SessionContextEntry(record_id="o", segment="output", content="o", created_seq=3)

    assert prior.segment == "prior"
    assert inp.segment == "input"
    assert out.segment == "output"


def test_session_context_entry_serialization():
    """SessionContextEntry to_dict and from_dict roundtrip."""
    entry = SessionContextEntry(
        record_id="entry-3",
        segment="output",
        content={"result": "data"},
        origin_record_id="orig-3",
        source_node_id="node-3",
        source_session_id="session-3",
        created_seq=3,
    )

    entry_dict = entry.to_dict()
    restored = SessionContextEntry.from_dict(entry_dict)

    assert restored.record_id == entry.record_id
    assert restored.segment == entry.segment
    assert restored.content == entry.content
    assert restored.origin_record_id == entry.origin_record_id
    assert restored.source_node_id == entry.source_node_id
    assert restored.source_session_id == entry.source_session_id
    assert restored.created_seq == entry.created_seq


def test_session_context_entry_auto_id():
    """SessionContextEntry generates record_id if not provided."""
    entry = SessionContextEntry(
        segment="prior",
        content="auto id test",
        created_seq=1,
    )

    assert entry.record_id is not None
    assert len(entry.record_id) == 32  # uuid4 hex length
