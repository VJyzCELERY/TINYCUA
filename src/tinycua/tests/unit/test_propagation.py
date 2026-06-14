"""Integration tests for propagation and dedupe."""

from tinycua.models.chat_record import ChatRecord
from tinycua.models.session_context_entry import SessionContextEntry
from tinycua.models.session import Session
from tinycua.loops.propagation import (
    propagate_on_termination,
    finalize_terminal_output,
    dedupe_records,
    PROPAGATION_PROFILES,
)


def test_propagation_upward_and_forwarding():
    """On node termination, prior+input propagate upward, output forwards to next."""
    # Arrange
    root_session = Session(
        session_id="root", chat_history=[], session_context=[], input_context=[]
    )
    parent_session = Session(
        session_id="parent",
        parent_id="root",
        chat_history=[],
        session_context=[],
        input_context=[],
    )
    node_session = Session(
        session_id="node1",
        parent_id="parent",
        chat_history=[],
        session_context=[],
        input_context=[],
    )

    prior = SessionContextEntry(
        record_id="prior-1",
        content="prior context",
        segment="prior",
        source_node_id="n0",
        created_seq=1,
    )
    inp = SessionContextEntry(
        record_id="input-1",
        content="input data",
        segment="input",
        source_node_id="n1",
        created_seq=2,
    )
    out = SessionContextEntry(
        record_id="output-1",
        content="output result",
        segment="output",
        source_node_id="n1",
        created_seq=3,
    )
    node_session.session_context = [prior, inp, out]

    rule = PROPAGATION_PROFILES["natural_termination_legacy"]

    # Act
    propagate_on_termination(node_session, parent_session, root_session, rule)

    # Assert — output NOT in parent/root (forwarded to next node)
    parent_contents = [e.content for e in parent_session.session_context]
    root_contents = [e.content for e in root_session.session_context]
    assert "prior context" in parent_contents
    assert "input data" in parent_contents
    assert "output result" not in parent_contents
    assert "output result" not in root_contents


def test_dedupe_on_propagation_filters_duplicates():
    """When dedupe=True, records with matching origin_record_id are filtered."""
    # Arrange
    root_session = Session(
        session_id="root", chat_history=[], session_context=[], input_context=[]
    )
    parent_session = Session(
        session_id="parent",
        parent_id="root",
        chat_history=[],
        session_context=[],
        input_context=[],
    )
    node_session = Session(
        session_id="node1",
        parent_id="parent",
        chat_history=[],
        session_context=[],
        input_context=[],
    )

    existing = SessionContextEntry(
        record_id="existing-1",
        content="already propagated",
        segment="prior",
        source_node_id="n0",
        origin_record_id="orig-123",
        created_seq=1,
    )
    parent_session.session_context = [existing]

    duplicate = SessionContextEntry(
        record_id="dup-1",
        content="already propagated",
        segment="prior",
        source_node_id="n0",
        origin_record_id="orig-123",
        created_seq=2,
    )
    fresh = SessionContextEntry(
        record_id="fresh-1",
        content="new context",
        segment="input",
        source_node_id="n1",
        origin_record_id="orig-456",
        created_seq=3,
    )
    node_session.session_context = [duplicate, fresh]

    rule = PROPAGATION_PROFILES["natural_termination_legacy"]

    # Act
    propagate_on_termination(node_session, parent_session, root_session, rule)

    # Assert — duplicate filtered, fresh added
    contents = [e.content for e in parent_session.session_context]
    assert contents.count("already propagated") == 1
    assert "new context" in contents


def test_terminal_output_exception():
    """Terminal output is committed to root session_context and returned, not forwarded."""
    root_session = Session(
        session_id="root", chat_history=[], session_context=[], input_context=[]
    )
    terminal_session = Session(
        session_id="terminal",
        parent_id="root",
        chat_history=[],
        session_context=[],
        input_context=[],
    )

    out = SessionContextEntry(
        record_id="out-1",
        content="final answer",
        segment="output",
        source_node_id="resp1",
        created_seq=1,
    )
    prior = SessionContextEntry(
        record_id="prior-2",
        content="context",
        segment="prior",
        source_node_id="resp1",
        created_seq=2,
    )
    terminal_session.session_context = [prior, out]

    result = finalize_terminal_output(terminal_session, root_session)

    # Assert — output committed to root
    root_contents = [e.content for e in root_session.session_context]
    assert "final answer" in root_contents
    assert result == "final answer"


def test_chat_record_appended_during_propagation():
    """ChatRecord is appended to chat_history per PropagationRule.chat_history."""
    root_session = Session(
        session_id="root", chat_history=[], session_context=[], input_context=[]
    )
    parent_session = Session(
        session_id="parent",
        parent_id="root",
        chat_history=[],
        session_context=[],
        input_context=[],
    )
    node_session = Session(
        session_id="node1",
        parent_id="parent",
        chat_history=[],
        session_context=[],
        input_context=[],
    )

    out = SessionContextEntry(
        content="result", segment="output", source_node_id="n1", created_seq=1
    )
    node_session.session_context = [out]

    rule = PROPAGATION_PROFILES["natural_termination_legacy"]

    # Act
    propagate_on_termination(node_session, parent_session, root_session, rule)

    # Assert — ChatRecord appended to both parent and root chat_history
    assert len(parent_session.chat_history) > 0
    assert len(root_session.chat_history) > 0
    assert isinstance(parent_session.chat_history[0], ChatRecord)
    assert parent_session.chat_history[0].record_type == "propagation"


def test_empty_output_no_forwarding():
    """Empty output segment does not cause forwarding; prior+input still propagate."""
    root_session = Session(
        session_id="root", chat_history=[], session_context=[], input_context=[]
    )
    parent_session = Session(
        session_id="parent",
        parent_id="root",
        chat_history=[],
        session_context=[],
        input_context=[],
    )
    node_session = Session(
        session_id="node1",
        parent_id="parent",
        chat_history=[],
        session_context=[],
        input_context=[],
    )

    prior = SessionContextEntry(
        record_id="prior-3",
        content="prior",
        segment="prior",
        source_node_id="n0",
        created_seq=1,
    )
    node_session.session_context = [prior]

    rule = PROPAGATION_PROFILES["natural_termination_legacy"]

    # Act — no output segment
    propagate_on_termination(node_session, parent_session, root_session, rule)

    # Assert — prior propagated to parent
    contents = [e.content for e in parent_session.session_context]
    assert "prior" in contents


def test_dedupe_records_by_origin_record_id():
    """dedupe_records filters by origin_record_id when present."""
    source = [
        SessionContextEntry(
            record_id="copy-1",
            content="copy1",
            segment="prior",
            origin_record_id="orig-1",
            created_seq=1,
        ),
        SessionContextEntry(
            record_id="copy-2",
            content="copy2",
            segment="input",
            origin_record_id="orig-2",
            created_seq=2,
        ),
    ]
    destination = [
        SessionContextEntry(
            record_id="exist-1",
            content="existing",
            segment="prior",
            origin_record_id="orig-1",
            created_seq=0,
        ),
    ]

    result = dedupe_records(source, destination)

    # orig-1 filtered (already exists), orig-2 kept
    assert len(result) == 1
    assert result[0].origin_record_id == "orig-2"


def test_dedupe_falls_back_to_record_id():
    """dedupe_records falls back to record_id when origin_record_id is None."""
    source = [
        SessionContextEntry(
            content="item",
            segment="prior",
            record_id="id-abc",
            origin_record_id=None,
            created_seq=1,
        ),
    ]
    destination = [
        SessionContextEntry(
            content="item",
            segment="prior",
            record_id="id-abc",
            origin_record_id=None,
            created_seq=0,
        ),
    ]

    result = dedupe_records(source, destination)
    assert len(result) == 0  # filtered by record_id match


def test_propagation_profiles_all_defined():
    """All four required profiles are defined with correct field values."""
    assert "transient_legacy" in PROPAGATION_PROFILES
    assert "natural_termination_legacy" in PROPAGATION_PROFILES
    assert "mid_progress_legacy" in PROPAGATION_PROFILES
    assert "selected_internal_output" in PROPAGATION_PROFILES

    t = PROPAGATION_PROFILES["transient_legacy"]
    assert t.session_context_target == "none"
    assert t.session_context_mode == "none"

    nt = PROPAGATION_PROFILES["natural_termination_legacy"]
    assert nt.session_context_target == "parent_and_root"
    assert nt.session_context_mode == "final"

    mp = PROPAGATION_PROFILES["mid_progress_legacy"]
    assert mp.chat_history == "parent_and_root"
    assert mp.session_context_mode == "full"
    assert mp.dedupe is True

    si = PROPAGATION_PROFILES["selected_internal_output"]
    assert si.chat_history == "root"
    assert si.session_context_target == "root"
    assert si.session_context_mode == "selected"


def test_node_message_policy_dedupe_by_origin():
    """NodeMessagePolicy.dedupe_by_origin_record_id filters duplicates from LLM input."""
    from tinycua.loops.node import build_messages_with_dedupe

    session = Session(
        session_id="s1", chat_history=[], session_context=[], input_context=[]
    )
    e1 = SessionContextEntry(
        record_id="e1",
        content="ctx1",
        segment="prior",
        origin_record_id="orig-1",
        created_seq=1,
    )
    e2 = SessionContextEntry(
        record_id="e2",
        content="ctx2",
        segment="input",
        origin_record_id="orig-2",
        created_seq=2,
    )
    e3 = SessionContextEntry(
        record_id="e3",
        content="ctx1-dup",
        segment="prior",
        origin_record_id="orig-1",
        created_seq=3,
    )
    session.session_context = [e1, e2, e3]

    messages = build_messages_with_dedupe(session, dedupe_by_origin_record_id=True)

    # Only 2 unique entries (by origin_record_id)
    context_msgs = [m for m in messages if m.get("role") == "user"]
    assert len(context_msgs) == 2
    contents = [m.get("content") for m in context_msgs]
    assert "ctx1" in contents
    assert "ctx2" in contents


def test_segmented_context_creation():
    """SessionContextEntry supports all three segment values."""
    prior = SessionContextEntry(
        record_id="seg-p", content="p", segment="prior", created_seq=1
    )
    inp = SessionContextEntry(
        record_id="seg-i", content="i", segment="input", created_seq=2
    )
    out = SessionContextEntry(
        record_id="seg-o", content="o", segment="output", created_seq=3
    )
    assert prior.segment == "prior"
    assert inp.segment == "input"
    assert out.segment == "output"
