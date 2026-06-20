"""Tests for runtime context in TinyCUA node prompts.

Phase 3 (FR-015/FR-016): the system prompt is byte-stable across calls (no
per-call timestamp) so prompt-cache prefixes hold on llama.cpp / OpenAI. The
current date/time moves to a volatile USER message in the suffix.
"""

from datetime import UTC, datetime

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.system_prompt import build_runtime_context
from tinycua.loops.node import ProcessNode
from tinycua.models.session import Session


def test_build_runtime_context_is_stable_without_timestamp() -> None:
    """Runtime context is constant — no per-call timestamp (FR-015).

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


def test_system_prompt_is_byte_stable_across_calls() -> None:
    """Two consecutive build_system_message calls return identical bytes (FR-016)."""
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")

    first = node.build_system_message()
    second = node.build_system_message()

    assert first == second, "system message must be byte-stable across calls"


def test_timestamp_lives_in_user_message_not_system() -> None:
    """Current date/time is in a USER message (volatile suffix), not the system prompt."""
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")

    messages = node.build_messages(Session(), {})

    system = messages[0]
    assert system["role"] == "system"
    assert "Do the task." in system["content"]
    assert "## Runtime Context" in system["content"]
    # The timestamp must NOT be in the system message.
    assert "Current date/time:" not in system["content"]

    # The timestamp must be in a user message in the suffix.
    user_msgs = [m for m in messages if m["role"] == "user"]
    assert any("Current date/time:" in m["content"] for m in user_msgs), (
        "timestamp must appear in a user message"
    )


def test_system_prefix_stable_while_timestamp_varies() -> None:
    """The system message stays identical even as time advances between calls."""
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    sys1 = node.build_system_message()
    # Simulate a later call — system message cached, should be identical.
    sys2 = node.build_system_message()
    assert sys1 == sys2