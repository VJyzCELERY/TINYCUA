"""Tests for runtime context in TinyCUA node prompts.

Phase 3 (FR-015/FR-016): the system prompt is byte-stable across calls (no
per-call timestamp) so prompt-cache prefixes hold on llama.cpp / OpenAI. The
slow-moving date (session-scoped snapshot) lives in the stable system prefix;
the fast-moving time-of-day lives in a volatile USER message in the suffix.
"""

from datetime import UTC, datetime

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.system_prompt import build_runtime_context
from tinycua.loops.node import ProcessNode
from tinycua.models.session import Session


def test_build_runtime_context_is_stable_without_timestamp() -> None:
    """Runtime context without a snapshot is constant — no per-call timestamp (FR-015).

    The ``now`` arg is accepted for backward-compat but ignored; the context
    is byte-stable so the system prefix can be prompt-cached.
    """
    a = build_runtime_context(datetime(2026, 6, 19, 5, 0, tzinfo=UTC))
    b = build_runtime_context(datetime(2027, 1, 1, 0, 0, tzinfo=UTC))
    c = build_runtime_context()

    assert a == b == c, "runtime context must be byte-stable across calls"
    assert "## Runtime Context" in a
    # No timestamp fragments leak into the stable system context.
    assert "Current date/time:" not in a
    assert "Timezone:" not in a
    assert "Today:" not in a  # no snapshot → no date line


def test_build_runtime_context_includes_date_snapshot() -> None:
    """When date_snapshot is provided, it appears as `Today: <snapshot>`."""
    ctx = build_runtime_context(date_snapshot="2026-06-21 (Sunday)")
    assert "## Runtime Context" in ctx
    assert "Today: 2026-06-21 (Sunday)" in ctx


def test_system_prompt_is_byte_stable_across_calls() -> None:
    """Two consecutive build_system_message calls return identical bytes (FR-016)."""
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")

    first = node.build_system_message()
    second = node.build_system_message()

    assert first == second, "system message must be byte-stable across calls"


def test_time_lives_in_user_message_date_in_system() -> None:
    """Date snapshot is in the SYSTEM message; time-of-day is in a USER message."""
    session = Session()
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    node.ensure_session(session)

    messages = node.build_messages(session, {})

    system = messages[0]
    assert system["role"] == "system"
    assert "Do the task." in system["content"]
    assert "## Runtime Context" in system["content"]
    # The date snapshot must be in the system message.
    assert "Today:" in system["content"]
    # The time-of-day must NOT be in the system message.
    assert "Current time:" not in system["content"]
    # The old phrasing must not appear anywhere.
    assert "Current date/time:" not in system["content"]

    # The time-of-day must be in a user message in the suffix.
    user_msgs = [m for m in messages if m["role"] == "user"]
    assert any("Current time:" in m["content"] for m in user_msgs), (
        "time-of-day must appear in a user message"
    )


def test_system_prefix_stable_while_timestamp_varies() -> None:
    """The system message stays identical even as time advances between calls."""
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    sys1 = node.build_system_message()
    # Simulate a later call — system message cached, should be identical.
    sys2 = node.build_system_message()
    assert sys1 == sys2


def test_system_message_includes_date_snapshot_from_session() -> None:
    """The system message includes the session's date snapshot as `Today: ...`."""
    session = Session()
    session.date_snapshot = "2026-06-21 (Sunday)"
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    node.ensure_session(session)

    system = node.build_system_message()
    assert "Today: 2026-06-21 (Sunday)" in system["content"]


def test_child_session_inherits_root_date_snapshot() -> None:
    """ensure_session copies the root's date snapshot to the child session."""
    root = Session()
    root.date_snapshot = "2026-06-21 (Sunday)"
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")

    child = node.ensure_session(root)

    assert child.date_snapshot == "2026-06-21 (Sunday)"
    # And the node's system message picks it up.
    system = node.build_system_message()
    assert "Today: 2026-06-21 (Sunday)" in system["content"]


def test_system_prompt_differs_across_sessions_with_different_snapshots() -> None:
    """Two sessions with different snapshots produce different system messages."""
    session_a = Session()
    session_a.date_snapshot = "2026-06-21 (Sunday)"
    node_a = ProcessNode("a", NodeConfigBase(), instruction="Do the task.")
    node_a.ensure_session(session_a)

    session_b = Session()
    session_b.date_snapshot = "2027-01-01 (Friday)"
    node_b = ProcessNode("b", NodeConfigBase(), instruction="Do the task.")
    node_b.ensure_session(session_b)

    sys_a = node_a.build_system_message()
    sys_b = node_b.build_system_message()
    assert sys_a != sys_b
    assert "Today: 2026-06-21 (Sunday)" in sys_a["content"]
    assert "Today: 2027-01-01 (Friday)" in sys_b["content"]
